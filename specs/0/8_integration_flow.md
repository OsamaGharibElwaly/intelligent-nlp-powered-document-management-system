# Phase 8 — System Integration Specification

## 🎯 Objective
Connect all system components into a full RAG pipeline.

---

## 🔁 End-to-End Flow

### Upload Flow
File → Parser → Chunker → Embeddings → Vector DB

### Query Flow
Question → Embedding → Retrieval → Prompt Builder → Groq → Answer

---

## 🚫 Constraints
- No bypassing of retrieval layer
- No direct LLM calls from API
- All steps must be executed in sequence

---

## 🧠 System Behavior
- Fully deterministic pipeline execution
- Stateless query processing
- Modular service communication only

---

## ✅ Acceptance Criteria
- Upload → query flow works end-to-end
- No missing pipeline step
- Consistent output format across runs