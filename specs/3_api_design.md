# Phase 3 — API Specification

## 🎯 Objective
Define strict REST API contracts.

---

## 📌 Endpoints

### POST /upload

#### Input
multipart/form-data:
- file: PDF | DOCX | TXT

#### Output
```json
{
  "document_id": "string",
  "status": "processed"
}