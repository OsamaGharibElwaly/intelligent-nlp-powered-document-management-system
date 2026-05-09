## 🔸 Sub-Phase 2.3: Source Confidence & Explainability

### 🎯 Purpose
Increase user trust by making answers **traceable and explainable**.

### 📥 Input
- Retrieved chunks
- Relevance scores
- Final answer structure

### 📤 Output
- Confidence score for the answer
- Highlighted text spans used from documents

### ⚙️ Functional Requirements
- Compute confidence score based on:
  - Number of supporting sources
  - Agreement between retrieved chunks
  - Relevance scores
- Highlight exact spans used in answers
- Map:
  answer → document → chunk → text span

### 📐 Rules
- Confidence must be explainable and reproducible
- Highlighting must not modify original text

### ✅ Acceptance Criteria
- Users can trace each claim to a document span
- Confidence score reflects robustness of evidence
