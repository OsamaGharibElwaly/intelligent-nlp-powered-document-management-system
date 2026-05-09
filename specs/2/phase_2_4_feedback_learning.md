## 🔸 Sub-Phase 2.4: Feedback Loop & Learning Signals

### 🎯 Purpose
Continuously improve retrieval quality using real user feedback.

### 📥 Input
- User feedback:
  - 👍 Positive
  - 👎 Negative
- Failed or low-confidence queries

### 📤 Output
- Stored feedback records
- Retrieval improvement signals

### ⚙️ Functional Requirements
- Store feedback linked to:
  - query
  - retrieved chunks
  - final answer
- Log failed or unanswered queries
- Use feedback to:
  - adjust retrieval ranking weights
  - flag documents for re-indexing

### 📐 Rules
- Feedback must not alter past answers
- Improvements apply only to future queries

### ✅ Acceptance Criteria
- Feedback is persisted correctly
- System improves retrieval over time
- Failed queries are traceable and analyzable