# [Service Name] Design

---

## Writing Guidelines for Design Documents

**For AI Assistants and Authors:**

1. **Use Precise Technical Language:**
   - Avoid metaphors (e.g., "acts as the brain", "serves as the hands"). Instead, describe the exact technical function.
   - Replace vague terms with specific technical descriptions (e.g., "centralized data persistence layer" instead of "long-term memory").

2. **Define Terms in a Glossary:**
   - Add a "0.1 Glossary" section immediately after "Customer Purpose & High-Level Overview".
   - Include all domain-specific terms, protocols, and technologies used in the document.
   - Provide concrete examples where applicable (e.g., list specific MCP servers, tools, or libraries).

3. **Scope the Glossary Appropriately:**
   - Only include terms relevant to THIS service. Do not copy terms from other services unless they directly interact with this one.
   - For example: Context Service should not define LangGraph (used only in Orchestrator).

4. **Be Explicit About Responsibilities:**
   - Clearly state what this service does and does NOT do.
   - Specify which components manage which data or processes.

5. **Maintain Consistency:**
   - Use the same terminology throughout the document.
   - Ensure glossary definitions match usage in the body text.

6. **Use Consistent Section Numbering:**
   - Number all sections and subsections using hierarchical decimal notation: `0.`, `0.1`, `1.`, `1.1`, `1.2`, `1.2.1`, `2.`, `2.1`, etc.
   - Main sections use single digits (0, 1, 2, ...).
   - Subsections use decimal notation (1.1, 1.2, 2.1, 2.2, ...).
   - Sub-subsections add another level (1.1.1, 1.2.1, 2.1.1, ...).
   - This hierarchical structure aids quick skimming by segregating complexity within subsections and organizing topics across sections.
   - Example: "## 2. Architecture & Internal Design" → "### 2.1 Component Name" → "#### 2.1.1 Specific Detail".



---


## 0. Customer Purpose & High-Level Overview

[Describe the primary purpose of this service from a customer/user perspective. What problem does it solve? Why does it exist? Use precise technical language—avoid metaphors.]

### 0.1 Glossary

*   **[Service Name]:** [Technical definition of this service's role and responsibilities]
*   **[Key Term 1]:** [Definition with examples if applicable]
*   **[Key Term 2]:** [Definition with examples if applicable]
*   **[Protocol/Technology]:** [Definition, version, and purpose]


### Core Value Propositions
1.  **[Value Prop 1]:** [Description]
2.  **[Value Prop 2]:** [Description]
3.  **[Value Prop 3]:** [Description]

### High-Level Strategy
*   **MVP (P0 - Steel Thread):** [Describe the minimal viable scope for the initial release. What is the "steel thread" use case?]
*   **Production (P1 - Extension):** [Describe the vision for the full production version. What capabilities will be added?]

## 1. System Requirements

To achieve the value propositions, the [Service Name] must:

1.  **[Requirement 1]:** [Description]
2.  **[Requirement 2]:** [Description]
3.  **[Requirement 3]:** [Description]

## 2. Architecture & Internal Design

[Describe the internal structure of the service. What are the key components or layers? Use diagrams or text descriptions.]

### [Component/Layer 1]
*   **Role:** [What does this component do?]
*   **Responsibility:**
    *   **[Responsibility A]:** [Detail]
    *   **[Responsibility B]:** [Detail]

### [Component/Layer 2]
*   ...

## 3. Interfaces & Interactions

[Describe how this service interacts with other parts of the system. Define the inputs and outputs.]

### 3.1 Interaction with [Other Service A]
*   **[Action Type]:**
    *   **Trigger:** [What causes this interaction?]
    *   **Action:** [What is the specific call or message?]
    *   **Data:** [What data is exchanged?]

### 3.2 API Interface (If applicable)
*   `[METHOD] /path`: [Description]

## 4. Technology Stack & Trade-offs

[List the key technologies chosen and the rationale behind them.]

### [Technology A]
*   **Why:** [Reason for selection]
*   **Trade-off:** [Potential downsides and mitigations]

## 5. External Dependencies

[List external systems or services this service relies on.]

### 5.1 [Dependency Category]
*   **[Dependency Name]:** [Description]

## 6. Operational Considerations

[Discuss safeguards, error handling, limitations, and security measures.]

### 6.1 Error Handling
*   **[Failure Scenario]:** [Recovery strategy]

### 6.2 Safety & Security
*   **[Measure]:** [Description]

## 7. Future Roadmap & Alternatives

[Discuss future migration paths or alternative designs considered.]

### [Alternative A]
*   **Why:** [Pros]
*   **Trade-off:** [Cons]

## 8. Implementation Roadmap

### 8.1 Phase 1: MVP (P0) - The "Steel Thread"
**Goal:** [Specific goal for MVP]

1.  **[Step 1]:** [Details]
2.  **[Step 2]:** [Details]

### 8.2 Extension to Production (P1)
**Goal:** [Specific goal for Production]

1.  **[Step 1]:** [Details]
2.  **[Step 2]:** [Details]
