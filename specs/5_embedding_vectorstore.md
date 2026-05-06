# Phase 5 — Embedding & Vector Store Specification

## 🎯 Objective
Transform text chunks into embeddings and store them in FAISS for retrieval.

---

## 📥 Input
[
  {
    "chunk_id": string,
    "text": string
  }
]

---

## 📤 Output
- FAISS index populated
- Metadata mapping stored

---

## 🧠 Embedding Model
- SentenceTransformer: all-MiniLM-L6-v2

---

## 🔧 Process
1. Convert text → embedding vector
2. Normalize vectors
3. Store in FAISS index
4. Map vector → chunk metadata

---

## 🚫 Constraints
- Must be deterministic
- No external vector DB
- No randomness allowed

---

## 🧠 System Behavior
- Same input always produces same vector
- Embeddings must be reusable across queries

---

## ✅ Acceptance Criteria
- All chunks are embedded successfully
- FAISS index is searchable
- Retrieval returns valid vectors