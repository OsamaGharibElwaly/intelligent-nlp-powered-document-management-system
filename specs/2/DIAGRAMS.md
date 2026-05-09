# Phase 2 — Mermaid diagrams (AI & Retrieval Intelligence)

Diagrams summarize **`specs/2`** sub-phases and how they chain in one pipeline.

---

## Phase 2 — End-to-end pipeline (single request)

```mermaid
flowchart TB
    Q[POST /query<br/>question + document_id<br/>optional document_ids + filters<br/>retrieval_mode + answer_mode + answer_length]

    subgraph Scope["Scope resolution"]
        RQ[resolve_query_documents]
        MAP[build_metadata_by_active_indexes<br/>logical doc → index_document_id]
    end

    subgraph Ret["2.1 Retrieval Engine"]
        HY[Hybrid: keyword norm + vector norm]
        W[Learned hybrid weights]
        D[Per-chunk relevance delta]
        RK[Deterministic rank top_k]
    end

    subgraph Ans["2.2 Answer generation"]
        PB[PromptBuilder.build_answer<br/>JSON paragraphs contract]
        LLM[LLMService.answer_json Groq]
        ST[Strict verbatim enforcement]
    end

    subgraph Exp["2.3 Explainability"]
        CF[Answer confidence<br/>support + relevance + agreement]
        EV[Evidence spans<br/>verbatim chunk offsets]
    end

    subgraph FB["2.4 Feedback future-only"]
        AUD_Q[query_quality_issue audit<br/>if low confidence / empty answer]
        PF[POST /feedback snapshots]
        LS[(learning_signals.json)]
    end

    Q --> RQ --> MAP
    MAP --> HY
    W --> HY
    D --> HY
    HY --> RK --> PB --> LLM --> ST
    ST --> CF
    ST --> EV
    CF --> AUD_Q
    Q -. after user .-> PF --> LS
    LS -. next query .-> W
    LS -. next query .-> D
```

---

## 2.1 — Hybrid retrieval scoring (conceptual)

```mermaid
flowchart LR
    subgraph Inputs
        TXT[Chunk texts]
        QE[Query embedding]
        F[Metadata pre-filter<br/>reduces chunk set only]
    end

    subgraph Score["Per chunk"]
        KW[Keyword score<br/>terms + exact phrase boost]
        VS[Vector score<br/>FAISS inner product]
        BL[Blend kw_w·KW + vec_w·VS<br/>weights from learning store]
        AD[+ chunk_relevance_delta]
    end

    TXT --> KW
    QE --> VS
    F --> TXT
    KW --> BL
    VS --> BL
    BL --> AD
    AD --> SORT[Sort: exact match,<br/>relevance, ties deterministic]
```

---

## 2.2 — Answer modes

```mermaid
flowchart TB
    M{answer_mode}

    M -->|strict| S[Paragraphs must be<br/>verbatim from CONTEXT]
    M -->|flexible| F[Synthesis allowed<br/>must cite chunks per paragraph]

    S --> OUT[JSON paragraphs + citations]
    F --> OUT
    OUT --> PB_FALLBACK[Invalid JSON / HTTP →<br/>fallback grounded excerpt]
```

---

## 2.3 — Confidence & evidence spans

```mermaid
flowchart TB
    subgraph Conf["Confidence formula v2.3.0-v1"]
        SUP[Supporting unique chunks]
        REL[Mean relevance of cited chunks / max retrieval]
        AGR[Pairwise token Jaccard<br/>between cited chunk texts]
        SC[0.25·SUP + 0.45·REL + 0.30·AGR → score ∈ 0..1]
    end

    subgraph Ev["Evidence spans"]
        P[Each paragraph × each citation]
        L[Longest contiguous substring<br/>of paragraph in chunk_text]
        SP[span_start:end + span_text copy<br/>original doc unchanged]
    end

    CIT[Citations from LLM] --> SUP
    RET[Retrieved chunks] --> REL
    CHK[Chunk texts for cited ids] --> AGR
    SUP --> SC
    REL --> SC
    AGR --> SC

    P --> L --> SP
```

---

## 2.4 — Feedback loop (past answers immutable)

```mermaid
flowchart LR
    subgraph Write["On POST /feedback"]
        REC[(feedback.jsonl)]
        CHΔ[chunk_relevance_delta ± step capped]
        HW[nudge hybrid_keyword / vector weights]
        RQ[reindex_queue flag<br/>on negative + low conf / no answer]
    end

    subgraph Next["Next retrieval only"]
        RE[RetrievalEngine reads<br/>LearningSignalsStore]
    end

    REC --> CHΔ --> RE
    REC --> HW --> RE
    REC --> RQ
```
