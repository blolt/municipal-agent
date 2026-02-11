-- Migration 002: Setup Apache AGE Extension and Graph Schema
-- Creates the knowledge graph structure for RAG

CREATE EXTENSION IF NOT EXISTS age;

-- Load the AGE extension
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Create the knowledge graph
SELECT create_graph('knowledge_graph');

-- Create Vertex Labels (Entities)
SELECT create_vlabel('knowledge_graph', 'Entity');
SELECT create_vlabel('knowledge_graph', 'Person');
SELECT create_vlabel('knowledge_graph', 'Order');
SELECT create_vlabel('knowledge_graph', 'Product');
SELECT create_vlabel('knowledge_graph', 'Ticket');

-- Create Edge Labels (Relationships)
SELECT create_elabel('knowledge_graph', 'CREATED');
SELECT create_elabel('knowledge_graph', 'ORDERED');
SELECT create_elabel('knowledge_graph', 'CONTAINS');
SELECT create_elabel('knowledge_graph', 'MENTIONS');

-- Verify graph creation
SELECT * FROM ag_graph;
