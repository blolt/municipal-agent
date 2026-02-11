"""Knowledge Graph repository — Apache AGE Cypher operations for municipal zoning data.

Translates the RDF/OWL ontology from strongtowns-detroit into property graph
operations on the ``municipal_knowledge`` AGE graph. All queries are scoped
by (Municipality {name, state}) so multiple cities can coexist.

Vertex labels: Municipality, CodeSection, ZoningDistrict, LandUse,
               DimensionalStandard, Definition, ExternalLaw
Edge labels:   HAS_CHILD, BELONGS_TO, PERMITS, CONDITIONALLY_PERMITS,
               HAS_STANDARD, DEFINED_IN, REFERENCES, CITES_EXTERNAL, IN_DISTRICT
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from context_service.db.connection import get_db_connection

GRAPH_NAME = "municipal_knowledge"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cypher_sql(cypher: str, *, columns: str = "result agtype") -> str:
    """Wrap a Cypher query in the AGE SQL envelope."""
    return f"SELECT * FROM cypher('{GRAPH_NAME}', $$ {cypher} $$) as ({columns});"


def _escape(value: str) -> str:
    """Escape characters for safe inclusion in Cypher string literals."""
    if value is None:
        return ""
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    return s


def _agtype_to_python(rows: list) -> list[dict[str, Any]]:
    """Convert asyncpg Row results with agtype columns to Python dicts."""
    results = []
    for row in rows:
        row_dict = {}
        for key, val in dict(row).items():
            if val is None:
                row_dict[key] = None
            elif isinstance(val, str):
                try:
                    row_dict[key] = json.loads(val)
                except (json.JSONDecodeError, ValueError):
                    row_dict[key] = val
            else:
                row_dict[key] = val
        results.append(row_dict)
    return results


# ---------------------------------------------------------------------------
# Graph bootstrap
# ---------------------------------------------------------------------------

class KnowledgeGraphRepository:
    """Data access layer for the municipal knowledge graph in Apache AGE."""

    @staticmethod
    async def ensure_graph() -> None:
        """Create the AGE graph and vertex/edge labels if they don't exist."""
        async with get_db_connection() as conn:
            # Ensure AGE extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS age;")
            await conn.execute("SET search_path = ag_catalog, '$user', public;")

            # Create graph (idempotent — check first)
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM ag_catalog.ag_graph WHERE name = $1)",
                GRAPH_NAME,
            )
            if not exists:
                await conn.execute(
                    f"SELECT create_graph('{GRAPH_NAME}');"
                )

            # Create vertex labels
            for label in [
                "Municipality", "CodeSection", "ZoningDistrict",
                "LandUse", "DimensionalStandard", "Definition", "ExternalLaw",
            ]:
                label_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM ag_catalog.ag_label "
                    "WHERE name = $1 AND graph = (SELECT graphid FROM ag_catalog.ag_graph WHERE name = $2))",
                    label, GRAPH_NAME,
                )
                if not label_exists:
                    await conn.execute(
                        f"SELECT create_vlabel('{GRAPH_NAME}', '{label}');"
                    )

            # Create edge labels
            for label in [
                "HAS_CHILD", "BELONGS_TO", "PERMITS", "CONDITIONALLY_PERMITS",
                "HAS_STANDARD", "DEFINED_IN", "REFERENCES", "CITES_EXTERNAL",
                "IN_DISTRICT",
            ]:
                label_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM ag_catalog.ag_label "
                    "WHERE name = $1 AND graph = (SELECT graphid FROM ag_catalog.ag_graph WHERE name = $2))",
                    label, GRAPH_NAME,
                )
                if not label_exists:
                    await conn.execute(
                        f"SELECT create_elabel('{GRAPH_NAME}', '{label}');"
                    )

    # ------------------------------------------------------------------
    # Municipality
    # ------------------------------------------------------------------

    @staticmethod
    async def get_or_create_municipality(name: str, state: str) -> dict[str, Any]:
        """Find or create a Municipality vertex."""
        name_e, state_e = _escape(name), _escape(state)
        now = datetime.now(timezone.utc).isoformat()

        async with get_db_connection() as conn:
            # Try to find existing
            rows = await conn.fetch(_cypher_sql(
                f"MATCH (m:Municipality {{name: '{name_e}', state: '{state_e}'}}) "
                f"RETURN m"
            ))
            if rows:
                return _agtype_to_python(rows)[0]

            # Create new
            rows = await conn.fetch(_cypher_sql(
                f"CREATE (m:Municipality {{name: '{name_e}', state: '{state_e}', "
                f"fetched_at: '{now}'}}) RETURN m"
            ))
            return _agtype_to_python(rows)[0]

    # ------------------------------------------------------------------
    # CodeSection ingestion
    # ------------------------------------------------------------------

    @staticmethod
    async def ingest_code_section(
        municipality: str,
        state: str,
        section_id: str,
        title: str,
        content: str,
        level: str,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a CodeSection vertex and link it to its municipality and parent."""
        muni_e = _escape(municipality)
        state_e = _escape(state)
        sid_e = _escape(section_id)
        title_e = _escape(title)
        content_e = _escape(content)
        level_e = _escape(level)

        async with get_db_connection() as conn:
            # Upsert the section node (AGE uses SET, not ON CREATE/ON MATCH SET)
            rows = await conn.fetch(_cypher_sql(
                f"MATCH (m:Municipality {{name: '{muni_e}', state: '{state_e}'}}) "
                f"MERGE (s:CodeSection {{section_id: '{sid_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                f"SET s.title = '{title_e}', s.level = '{level_e}', "
                f"s.raw_content = '{content_e}' "
                f"MERGE (s)-[:BELONGS_TO]->(m) "
                f"RETURN s"
            ))
            result = _agtype_to_python(rows)

            # Link to parent if provided
            if parent_id:
                parent_e = _escape(parent_id)
                await conn.fetch(_cypher_sql(
                    f"MATCH (p:CodeSection {{section_id: '{parent_e}', "
                    f"municipality: '{muni_e}', state: '{state_e}'}}) "
                    f"MATCH (c:CodeSection {{section_id: '{sid_e}', "
                    f"municipality: '{muni_e}', state: '{state_e}'}}) "
                    f"MERGE (p)-[:HAS_CHILD]->(c) "
                    f"RETURN p, c"
                ))

            return result[0] if result else {}

    # ------------------------------------------------------------------
    # Structured data ingestion
    # ------------------------------------------------------------------

    @staticmethod
    async def ingest_use_permissions(
        municipality: str,
        state: str,
        permissions: list[dict[str, Any]],
    ) -> int:
        """Store use-permission rows as ZoningDistrict→LandUse edges.

        Each permission dict: {use, district, level, conditions}
        level: "permitted", "conditional", "not_permitted"
        """
        muni_e = _escape(municipality)
        state_e = _escape(state)
        count = 0

        async with get_db_connection() as conn:
            for perm in permissions:
                use_e = _escape(perm["use"])
                dist_e = _escape(perm["district"])
                cond_e = _escape(perm.get("conditions", ""))
                level = perm.get("level", "permitted")

                # Ensure district node
                await conn.fetch(_cypher_sql(
                    f"MATCH (m:Municipality {{name: '{muni_e}', state: '{state_e}'}}) "
                    f"MERGE (d:ZoningDistrict {{code: '{dist_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                    f"MERGE (d)<-[:IN_DISTRICT]-(m) "
                    f"RETURN d"
                ))

                # Ensure use node
                await conn.fetch(_cypher_sql(
                    f"MERGE (u:LandUse {{name: '{use_e}'}}) RETURN u"
                ))

                # Create permission edge
                if level == "conditional":
                    edge_label = "CONDITIONALLY_PERMITS"
                elif level == "permitted":
                    edge_label = "PERMITS"
                else:
                    continue  # not_permitted = no edge

                review_e = _escape(perm.get("review_section", ""))
                await conn.fetch(_cypher_sql(
                    f"MATCH (d:ZoningDistrict {{code: '{dist_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                    f"MATCH (u:LandUse {{name: '{use_e}'}}) "
                    f"MERGE (d)-[:{edge_label} {{conditions: '{cond_e}', review_section: '{review_e}'}}]->(u) "
                    f"RETURN d, u"
                ))
                count += 1

        return count

    @staticmethod
    async def ingest_dimensional_standards(
        municipality: str,
        state: str,
        standards: list[dict[str, Any]],
    ) -> int:
        """Store dimensional standards as ZoningDistrict→DimensionalStandard edges.

        Each standard dict: {district, name, value, unit?, section_ref?}
        """
        muni_e = _escape(municipality)
        state_e = _escape(state)
        count = 0

        async with get_db_connection() as conn:
            for std in standards:
                dist_e = _escape(std["district"])
                name_e = _escape(std["name"])
                value_e = _escape(std["value"])
                unit_e = _escape(std.get("unit", ""))
                ref_e = _escape(std.get("section_ref", ""))

                # Ensure district node
                await conn.fetch(_cypher_sql(
                    f"MATCH (m:Municipality {{name: '{muni_e}', state: '{state_e}'}}) "
                    f"MERGE (d:ZoningDistrict {{code: '{dist_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                    f"MERGE (d)<-[:IN_DISTRICT]-(m) "
                    f"RETURN d"
                ))

                # Create standard node + edge
                await conn.fetch(_cypher_sql(
                    f"MATCH (d:ZoningDistrict {{code: '{dist_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                    f"MERGE (s:DimensionalStandard {{standard_type: '{name_e}', district: '{dist_e}', "
                    f"municipality: '{muni_e}', state: '{state_e}'}}) "
                    f"SET s.value = '{value_e}', s.unit = '{unit_e}', s.section_ref = '{ref_e}' "
                    f"MERGE (d)-[:HAS_STANDARD]->(s) "
                    f"RETURN s"
                ))
                count += 1

        return count

    @staticmethod
    async def ingest_definitions(
        municipality: str,
        state: str,
        definitions: list[dict[str, Any]],
    ) -> int:
        """Store zoning term definitions as Definition vertices.

        Each definition dict: {term, definition, section_ref?}
        """
        muni_e = _escape(municipality)
        state_e = _escape(state)
        count = 0

        async with get_db_connection() as conn:
            for defn in definitions:
                term_e = _escape(defn["term"])
                def_text_e = _escape(defn["definition"])
                ref_e = _escape(defn.get("section_ref", ""))

                # Create definition node
                await conn.fetch(_cypher_sql(
                    f"MERGE (d:Definition {{term: '{term_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                    f"SET d.definition_text = '{def_text_e}', d.section_ref = '{ref_e}' "
                    f"RETURN d"
                ))

                # Link to section if section_ref provided
                if ref_e:
                    await conn.fetch(_cypher_sql(
                        f"MATCH (d:Definition {{term: '{term_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                        f"MATCH (s:CodeSection {{section_id: '{ref_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                        f"MERGE (d)-[:DEFINED_IN]->(s) "
                        f"RETURN d, s"
                    ))

                count += 1

        return count

    # ------------------------------------------------------------------
    # Cross-references
    # ------------------------------------------------------------------

    @staticmethod
    async def add_cross_reference(
        municipality: str,
        state: str,
        source_section_id: str,
        target_section_id: str,
        relationship_type: str = "unknown",
        context: str = "",
        raw_citation: str = "",
    ) -> None:
        """Create a REFERENCES edge between two CodeSection nodes."""
        muni_e = _escape(municipality)
        state_e = _escape(state)
        src_e = _escape(source_section_id)
        tgt_e = _escape(target_section_id)
        rel_e = _escape(relationship_type)
        ctx_e = _escape(context)
        raw_e = _escape(raw_citation)

        async with get_db_connection() as conn:
            await conn.fetch(_cypher_sql(
                f"MATCH (a:CodeSection {{section_id: '{src_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                f"MATCH (b:CodeSection {{section_id: '{tgt_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                f"MERGE (a)-[:REFERENCES {{relationship_type: '{rel_e}', context: '{ctx_e}', "
                f"raw_citation: '{raw_e}'}}]->(b) "
                f"RETURN a, b"
            ))

    @staticmethod
    async def add_external_citation(
        municipality: str,
        state: str,
        source_section_id: str,
        law_id: str,
        law_type: str,
        raw_citation: str = "",
    ) -> None:
        """Create an ExternalLaw node and CITES_EXTERNAL edge."""
        muni_e = _escape(municipality)
        state_e = _escape(state)
        src_e = _escape(source_section_id)
        law_id_e = _escape(law_id)
        law_type_e = _escape(law_type)
        raw_e = _escape(raw_citation)

        async with get_db_connection() as conn:
            await conn.fetch(_cypher_sql(
                f"MATCH (s:CodeSection {{section_id: '{src_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                f"MERGE (e:ExternalLaw {{law_id: '{law_id_e}', law_type: '{law_type_e}'}}) "
                f"MERGE (s)-[:CITES_EXTERNAL {{raw_citation: '{raw_e}'}}]->(e) "
                f"RETURN s, e"
            ))

    # ------------------------------------------------------------------
    # Summary operations
    # ------------------------------------------------------------------

    @staticmethod
    async def update_summary(
        municipality: str,
        state: str,
        section_id: str,
        summary: str,
        summary_level: str,
    ) -> dict[str, Any]:
        """Update the summary fields on a CodeSection node."""
        muni_e = _escape(municipality)
        state_e = _escape(state)
        sid_e = _escape(section_id)
        summary_e = _escape(summary)
        level_e = _escape(summary_level)
        now = datetime.now(timezone.utc).isoformat()

        async with get_db_connection() as conn:
            rows = await conn.fetch(_cypher_sql(
                f"MATCH (s:CodeSection {{section_id: '{sid_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                f"SET s.summary = '{summary_e}', s.summary_level = '{level_e}', "
                f"s.summary_built_at = '{now}' "
                f"RETURN s"
            ))
            result = _agtype_to_python(rows)
            return result[0] if result else {}

    @staticmethod
    async def get_sections_for_summarization(
        municipality: str,
        state: str,
        scope: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get sections organized by level for bottom-up summarization.

        Returns sections grouped by level (section → division → article).
        If scope is provided, only return sections under that subtree.
        """
        muni_e = _escape(municipality)
        state_e = _escape(state)

        async with get_db_connection() as conn:
            if scope and scope != "all":
                scope_e = _escape(scope)
                # Get the subtree under a specific section
                rows = await conn.fetch(_cypher_sql(
                    f"MATCH (root:CodeSection {{section_id: '{scope_e}', "
                    f"municipality: '{muni_e}', state: '{state_e}'}})-[:HAS_CHILD*0..]->(s:CodeSection) "
                    f"RETURN s",
                    columns="s agtype",
                ))
            else:
                # Get all sections for the municipality
                rows = await conn.fetch(_cypher_sql(
                    f"MATCH (s:CodeSection {{municipality: '{muni_e}', state: '{state_e}'}}) "
                    f"RETURN s",
                    columns="s agtype",
                ))

            return _agtype_to_python(rows)

    @staticmethod
    async def get_children(
        municipality: str,
        state: str,
        section_id: str,
    ) -> list[dict[str, Any]]:
        """Get direct children of a section."""
        muni_e = _escape(municipality)
        state_e = _escape(state)
        sid_e = _escape(section_id)

        async with get_db_connection() as conn:
            rows = await conn.fetch(_cypher_sql(
                f"MATCH (p:CodeSection {{section_id: '{sid_e}', municipality: '{muni_e}', "
                f"state: '{state_e}'}})-[:HAS_CHILD]->(c:CodeSection) "
                f"RETURN c",
                columns="c agtype",
            ))
            return _agtype_to_python(rows)

    @staticmethod
    async def get_ancestors(
        municipality: str,
        state: str,
        section_id: str,
    ) -> list[dict[str, Any]]:
        """Get all ancestors of a section (parent chain to root)."""
        muni_e = _escape(municipality)
        state_e = _escape(state)
        sid_e = _escape(section_id)

        async with get_db_connection() as conn:
            rows = await conn.fetch(_cypher_sql(
                f"MATCH (a:CodeSection)-[:HAS_CHILD*]->"
                f"(s:CodeSection {{section_id: '{sid_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                f"RETURN a",
                columns="a agtype",
            ))
            return _agtype_to_python(rows)

    # ------------------------------------------------------------------
    # Query operations
    # ------------------------------------------------------------------

    @staticmethod
    async def get_section(
        municipality: str,
        state: str,
        section_id: str,
    ) -> dict[str, Any] | None:
        """Get a single CodeSection by ID."""
        muni_e = _escape(municipality)
        state_e = _escape(state)
        sid_e = _escape(section_id)

        async with get_db_connection() as conn:
            rows = await conn.fetch(_cypher_sql(
                f"MATCH (s:CodeSection {{section_id: '{sid_e}', municipality: '{muni_e}', "
                f"state: '{state_e}'}}) RETURN s",
                columns="s agtype",
            ))
            results = _agtype_to_python(rows)
            return results[0] if results else None

    @staticmethod
    async def query_permissions(
        municipality: str,
        state: str,
        district: str | None = None,
        use: str | None = None,
        permission_level: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query use permissions with optional filters."""
        muni_e = _escape(municipality)
        state_e = _escape(state)

        # Build dynamic match pattern
        dist_filter = f"{{code: '{_escape(district)}', municipality: '{muni_e}', state: '{state_e}'}}" if district else f"{{municipality: '{muni_e}', state: '{state_e}'}}"
        use_filter = f"{{name: '{_escape(use)}'}}" if use else ""

        # Query both PERMITS and CONDITIONALLY_PERMITS
        queries = []
        if not permission_level or permission_level == "permitted":
            queries.append(
                f"MATCH (d:ZoningDistrict {dist_filter})-[r:PERMITS]->(u:LandUse {use_filter}) "
                f"RETURN d.code as district, u.name as use_name, 'permitted' as permission_level, "
                f"r.conditions as conditions"
            )
        if not permission_level or permission_level == "conditional":
            queries.append(
                f"MATCH (d:ZoningDistrict {dist_filter})-[r:CONDITIONALLY_PERMITS]->(u:LandUse {use_filter}) "
                f"RETURN d.code as district, u.name as use_name, 'conditional' as permission_level, "
                f"r.conditions as conditions"
            )

        results = []
        async with get_db_connection() as conn:
            for q in queries:
                rows = await conn.fetch(_cypher_sql(
                    q,
                    columns="district agtype, use_name agtype, permission_level agtype, conditions agtype",
                ))
                results.extend(_agtype_to_python(rows))

        return results

    @staticmethod
    async def query_standards(
        municipality: str,
        state: str,
        district: str | None = None,
        standard_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query dimensional standards with optional filters."""
        muni_e = _escape(municipality)
        state_e = _escape(state)

        dist_filter = f"{{code: '{_escape(district)}', municipality: '{muni_e}', state: '{state_e}'}}" if district else f"{{municipality: '{muni_e}', state: '{state_e}'}}"
        std_filter = ""
        if standard_type:
            std_filter = f"{{standard_type: '{_escape(standard_type)}'}}"

        async with get_db_connection() as conn:
            rows = await conn.fetch(_cypher_sql(
                f"MATCH (d:ZoningDistrict {dist_filter})-[:HAS_STANDARD]->(s:DimensionalStandard {std_filter}) "
                f"RETURN d.code as district, s.standard_type as standard_type, "
                f"s.value as value, s.unit as unit, s.section_ref as section_ref",
                columns="district agtype, standard_type agtype, value agtype, unit agtype, section_ref agtype",
            ))
            return _agtype_to_python(rows)

    @staticmethod
    async def query_definition(
        municipality: str,
        state: str,
        term: str,
    ) -> dict[str, Any] | None:
        """Look up a zoning term definition."""
        muni_e = _escape(municipality)
        state_e = _escape(state)
        term_e = _escape(term)

        async with get_db_connection() as conn:
            rows = await conn.fetch(_cypher_sql(
                f"MATCH (d:Definition {{term: '{term_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                f"RETURN d.term as term, d.definition_text as definition, d.section_ref as section_ref",
                columns="term agtype, definition agtype, section_ref agtype",
            ))
            results = _agtype_to_python(rows)
            return results[0] if results else None

    @staticmethod
    async def traverse_hierarchy(
        municipality: str,
        state: str,
        start_section: str,
        direction: str = "down",
        depth: int = 3,
    ) -> list[dict[str, Any]]:
        """Walk the document tree from a starting point."""
        muni_e = _escape(municipality)
        state_e = _escape(state)
        start_e = _escape(start_section)

        async with get_db_connection() as conn:
            if direction == "up":
                rows = await conn.fetch(_cypher_sql(
                    f"MATCH (a:CodeSection)-[:HAS_CHILD*1..{depth}]->"
                    f"(s:CodeSection {{section_id: '{start_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                    f"RETURN a.section_id as section_id, a.title as title, a.level as level, "
                    f"a.summary as summary",
                    columns="section_id agtype, title agtype, level agtype, summary agtype",
                ))
            elif direction == "down":
                rows = await conn.fetch(_cypher_sql(
                    f"MATCH (s:CodeSection {{section_id: '{start_e}', municipality: '{muni_e}', "
                    f"state: '{state_e}'}})-[:HAS_CHILD*1..{depth}]->(c:CodeSection) "
                    f"RETURN c.section_id as section_id, c.title as title, c.level as level, "
                    f"c.summary as summary",
                    columns="section_id agtype, title agtype, level agtype, summary agtype",
                ))
            else:  # both
                # Up
                up_rows = await conn.fetch(_cypher_sql(
                    f"MATCH (a:CodeSection)-[:HAS_CHILD*1..{depth}]->"
                    f"(s:CodeSection {{section_id: '{start_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                    f"RETURN a.section_id as section_id, a.title as title, a.level as level, "
                    f"a.summary as summary",
                    columns="section_id agtype, title agtype, level agtype, summary agtype",
                ))
                # Down
                down_rows = await conn.fetch(_cypher_sql(
                    f"MATCH (s:CodeSection {{section_id: '{start_e}', municipality: '{muni_e}', "
                    f"state: '{state_e}'}})-[:HAS_CHILD*1..{depth}]->(c:CodeSection) "
                    f"RETURN c.section_id as section_id, c.title as title, c.level as level, "
                    f"c.summary as summary",
                    columns="section_id agtype, title agtype, level agtype, summary agtype",
                ))
                rows = list(up_rows) + list(down_rows)

            return _agtype_to_python(rows)

    @staticmethod
    async def find_related(
        municipality: str,
        state: str,
        section_id: str,
        relationship_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find cross-referenced sections and citation edges."""
        muni_e = _escape(municipality)
        state_e = _escape(state)
        sid_e = _escape(section_id)

        rel_filter = ""
        if relationship_type:
            rel_filter = f"{{relationship_type: '{_escape(relationship_type)}'}}"

        async with get_db_connection() as conn:
            # Outgoing references
            out_rows = await conn.fetch(_cypher_sql(
                f"MATCH (s:CodeSection {{section_id: '{sid_e}', municipality: '{muni_e}', "
                f"state: '{state_e}'}})-[r:REFERENCES {rel_filter}]->(t:CodeSection) "
                f"RETURN t.section_id as section_id, t.title as title, t.summary as summary, "
                f"r.relationship_type as relationship_type, r.context as context, "
                f"'outgoing' as direction",
                columns="section_id agtype, title agtype, summary agtype, "
                        "relationship_type agtype, context agtype, direction agtype",
            ))
            # Incoming references
            in_rows = await conn.fetch(_cypher_sql(
                f"MATCH (s:CodeSection)-[r:REFERENCES {rel_filter}]->"
                f"(t:CodeSection {{section_id: '{sid_e}', municipality: '{muni_e}', state: '{state_e}'}}) "
                f"RETURN s.section_id as section_id, s.title as title, s.summary as summary, "
                f"r.relationship_type as relationship_type, r.context as context, "
                f"'incoming' as direction",
                columns="section_id agtype, title agtype, summary agtype, "
                        "relationship_type agtype, context agtype, direction agtype",
            ))
            # External citations
            ext_rows = await conn.fetch(_cypher_sql(
                f"MATCH (s:CodeSection {{section_id: '{sid_e}', municipality: '{muni_e}', "
                f"state: '{state_e}'}})-[r:CITES_EXTERNAL]->(e:ExternalLaw) "
                f"RETURN e.law_id as law_id, e.law_type as law_type, "
                f"r.raw_citation as raw_citation, 'external' as direction",
                columns="law_id agtype, law_type agtype, raw_citation agtype, direction agtype",
            ))

            return (
                _agtype_to_python(list(out_rows))
                + _agtype_to_python(list(in_rows))
                + _agtype_to_python(list(ext_rows))
            )

    @staticmethod
    async def get_sections_by_level(
        municipality: str,
        state: str,
        level: str,
    ) -> list[dict[str, Any]]:
        """Get all sections at a given level (article, division, section)."""
        muni_e = _escape(municipality)
        state_e = _escape(state)
        level_e = _escape(level)

        async with get_db_connection() as conn:
            rows = await conn.fetch(_cypher_sql(
                f"MATCH (s:CodeSection {{level: '{level_e}', municipality: '{muni_e}', "
                f"state: '{state_e}'}}) "
                f"RETURN s.section_id as section_id, s.title as title, s.summary as summary, "
                f"s.raw_content as raw_content",
                columns="section_id agtype, title agtype, summary agtype, raw_content agtype",
            ))
            return _agtype_to_python(rows)
