# Phase 9 — Testing & Evaluation Specification

## 🎯 Objective
Validate correctness, determinism, and retrieval quality.

---

## 🧪 Test Cases

### 1. Upload Test
- valid file → processed successfully
- invalid file → rejected

---

### 2. Retrieval Test
- known query → correct chunk appears in top-K

---

### 3. LLM Grounding Test
- answer must be strictly based on retrieved context

---

### 4. Determinism Test
- same input → same output

---

## 📊 Metrics
- Retrieval accuracy
- Latency per query
- Context relevance score

---

## 🚫 Constraints
- No randomness allowed
- No external knowledge usage

---

## ✅ Acceptance Criteria
- All APIs function correctly
- Retrieval is consistent and relevant
- Answers are context-grounded
- System is stable under repeated runs