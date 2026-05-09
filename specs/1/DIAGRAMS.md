# Phase 1 — Mermaid diagrams (Foundation)

Diagrams summarize **`specs/1`** phases: auth, documents, versioning, metadata, audit, deployment.

---

## Phase 1 — Big picture

```mermaid
flowchart TB
    subgraph P1["Phase 1 Foundation"]
        A[1.1 User Management<br/>JWT + RBAC + quotas]
        B[1.2 Document Ownership<br/>upload + collections + STORAGE_PATH]
        C[1.3 Versioning & Lifecycle<br/>versions + soft delete + restore]
        D[1.4 Tags & Metadata<br/>PATCH metadata + filtering]
        E[1.5 Audit & Usage<br/>append-only audit.log]
        F[1.6 Deployment Ready<br/>Render / Vercel / env config]
    end
    A --> B --> C --> D
    B --> E
    C --> E
    D --> E
    E --> F
```

---

## 1.1 — Authentication & authorization

```mermaid
sequenceDiagram
    participant U as User / Frontend
    participant API as Backend API
    participant AUTH as AuthService / JWT

    U->>API: POST /auth/login (email, password)
    API->>AUTH: validate credentials + role
    AUTH-->>API: access_token + role + quotas
    API-->>U: JWT Bearer token + metadata

    U->>API: Protected route + Authorization header
    API->>AUTH: verify JWT + require_roles(...)
    AUTH-->>API: user claims sub, role
    API-->>U: 200 or 401/403
```

---

## 1.2 — Document ownership & upload

```mermaid
flowchart LR
    UP[POST /upload] --> VAL{Validate type & quota}
    VAL -->|ok| STORE[StorageService save bytes]
    STORE --> META[DocumentRepository.create<br/>owner_id + collection_id]
    META --> INGEST[IngestDocumentUseCase<br/>chunk + embed + FAISS]
    VAL -->|fail| ERR[400 / 403]
```

---

## 1.3 — Versioning & lifecycle

```mermaid
stateDiagram-v2
    [*] --> Active: create v1
    Active --> Active: append_version v2,v3...
    Active --> SoftDeleted: POST .../delete
    SoftDeleted --> Active: POST .../restore<br/>optional version pin
    note right of Active
      Active version points to
      index_document_id for retrieval
    end note
```

---

## 1.4 — Tags & metadata

```mermaid
flowchart TB
    PATCH[PATCH /documents/id/metadata] --> NORM[Normalize tags + kv metadata]
    NORM --> SAVE[metadata.json per STORAGE_PATH]
    SAVE --> LIST[GET /documents filters<br/>tag, metadata_key/value]
```

---

## 1.5 — Audit logging

```mermaid
flowchart LR
    EV[upload / query / feedback / ...] --> AUD[AuditService.log_event]
    AUD --> LOG[(audit.log append-only JSONL)]
    LOG --> USE[/audit/usage-history<br/>/audit/logs admin]
```

---

## 1.6 — Deployment topology

```mermaid
flowchart TB
    subgraph Local["Local dev"]
        FE[Next.js :3000]
        BE[FastAPI :8000]
        ST[(storage/)]
        FE --> BE
        BE --> ST
    end

    subgraph Prod["Production shape"]
        V[Vercel Frontend]
        R[Render Backend]
        VPS[(Persistent disk / STORAGE_PATH)]
        V --> R
        R --> VPS
    end
```
