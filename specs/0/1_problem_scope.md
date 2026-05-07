# Phase 1 — Problem Scope Specification

## 🎯 Objective
Design a RAG-based AI Document Assistant that allows users to upload documents and query them using natural language with grounded responses.

---

## 📌 System Definition
The system is a backend service that:
- Ingests documents (PDF, DOCX, TXT)
- Processes and chunks text
- Generates embeddings
- Stores vectors in a retrieval system
- Performs semantic search
- Uses Groq LLM API for answer generation

---

## 👥 Actors
- User (API consumer)

---

## 🚫 Out of Scope
- UI / frontend
- Authentication system (v1)
- Multi-tenant SaaS features
- Fine-tuning models
- Paid cloud services (vector DB SaaS)

---

## 🧠 Core Constraint
All answers MUST be derived from retrieved document context (RAG principle).
