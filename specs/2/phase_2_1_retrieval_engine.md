## 🔸 Sub-Phase 2.1: Retrieval Engine (Hybrid & Structured Search)

### 🎯 Purpose
Retrieve the most relevant document chunks using a combination of keyword search, vector similarity, and metadata filtering.

### 📥 Input
- User query (string)
- Optional filters:
  - date range
  - tags
  - author
- Retrieval mode (default or specified)

### 📤 Output
A ranked list of retrieved chunks:
- chunk_id
- document_id
- chunk_text
- relevance_score
- metadata (document, tags, date, author)

### ⚙️ Functional Requirements
- Support **hybrid retrieval**:
  - Keyword-based search (exact text match)
  - Vector-based semantic similarity
- Support **metadata-based filtering** before retrieval
- Allow retrieval across **multiple documents**
- Rank results using a combined relevance score

### 📐 Rules
- Exact keyword matches take priority
- Semantic similarity expands recall
- Metadata filters reduce search space, not re-rank results
- Retrieval must be deterministic for identical inputs

### ✅ Acceptance Criteria
- Same query + same data returns identical results
- Filters correctly exclude unrelated documents
- Hybrid search outperforms keyword-only search