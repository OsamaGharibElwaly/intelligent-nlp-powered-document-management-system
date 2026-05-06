# Phase 7 — LLM Integration Specification (Groq)

## 🎯 Objective
Generate final answers using Groq LLM based ONLY on retrieved context.

---

## 📥 Input
{
  "question": string,
  "context": [string]
}

---

## 📤 Output
{
  "answer": string
}

---

## 🧠 Prompt Structure

SYSTEM:
You are a grounded QA system. Answer ONLY using provided context.

CONTEXT:
{retrieved_chunks}

QUESTION:
{question}

---

## 🚫 Constraints
- Must NOT use external knowledge
- Must NOT hallucinate
- Must rely only on context

---

## 🧠 System Behavior
- If context is insufficient → return "Not enough information in document"
- Must remain deterministic per input

---

## ✅ Acceptance Criteria
- Answers are grounded in context
- No external inference occurs
- Output format is consistent