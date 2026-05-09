## :small_orange_diamond: Sub-Phase 2.2: Answer Generation & Control

### :dart: Purpose
Control **how answers are generated**, not just what is retrieved.

### :inbox_tray: Input
- Retrieved document chunks
- Answer mode:
  - Strict
  - Flexible
- Answer length preference (short / medium / detailed)

### :outbox_tray: Output
- Final answer text
- Structured citations per paragraph

### :gear: Functional Requirements
- Support answer modes:
  - **Strict Mode**
    - Uses only retrieved chunks verbatim
    - No inference outside provided text
  - **Flexible Mode**
    - Allows semantic reasoning across chunks
    - Combines ideas from multiple documents
- Control answer length
- Generate citations for each paragraph

### :triangular_ruler: Rules
- Strict mode must never hallucinate
- Flexible mode must still cite sources
- Every paragraph must reference at least one chunk

### :white_check_mark: Acceptance Criteria
- Strict answers are fully traceable to source text
- Flexible answers remain grounded and coherent
- Answer length matches user preference