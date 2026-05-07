# Phase 2 — System Architecture Specification

## 🎯 Objective
Define system components and enforce separation of concerns.

---

## 🧩 System Components

### API Layer
- FastAPI application
- Handles HTTP requests

### Document Processing Service
- Extracts raw text
- Normalizes content
- Splits into chunks

### Embedding Service
- Converts text chunks into embeddings
- Must be stateless

### Vector Store
- FAISS-based index
- Stores embeddings + metadata

### Retrieval Engine
- Performs similarity search
- Returns ranked chunks

### Prompt Builder
- Formats LLM input
- Injects context + query

### LLM Service
- Groq API integration

---

## 🔗 Architecture Rules

- API MUST NOT directly access vector DB
- All embedding logic MUST be inside Embedding Service
- LLM calls MUST only happen via Prompt Builder
- Each module MUST be independently testable
