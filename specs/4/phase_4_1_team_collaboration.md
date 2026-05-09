You are extending an existing FULL-STACK RAG Document Management System (Next.js frontend + backend API already implemented).

This is PHASE 4: Collaboration & Workflow.

DO NOT:
- Break existing authentication system
- Modify Phase 1–3 features
- Rewrite architecture
- Change backend core logic

ONLY EXTEND system with collaboration + workflow capabilities.

---

# 🟣 PHASE 4: COLLABORATION & WORKFLOW LAYER

## 🎯 OBJECTIVE

Transform the system from a single-user AI tool into a **multi-user collaborative workspace** where teams can:
- share documents
- collaborate on AI answers
- comment and discuss results
- receive real-time notifications on system events

---

# 👥 SUBPHASE 4.1: TEAM COLLABORATION CORE

## 🧠 GOAL
Introduce team-based collaboration around documents and AI queries.

---

## 📁 FEATURES

### 1. Shared Document Spaces
- Allow documents to belong to a "workspace" or "team"
- Each workspace contains multiple users

Data model additions:
- workspace_id
- owner_id
- members[]

---

### 2. Team-Based Permissions (RBAC Extension)
Roles inside workspace:
- owner
- editor
- viewer

Permissions:
- editor → upload, query, comment
- viewer → read + ask queries only

---

### 3. Shared Query Threads
- Each AI query becomes a "thread"
- Multiple users can view and continue discussion on same query

Thread includes:
- question
- AI answer
- follow-up messages

---

### 4. Commenting on AI Answers
- Users can comment directly on AI responses
- Comments are attached to:
  - document
  - query thread
  - or specific answer

---

## 🎨 FRONTEND UX REQUIREMENTS

- Add "Workspace Selector" in navbar
- Add "Team View" sidebar section
- Show shared documents separately from personal docs
- Add threaded conversation UI for queries
- Add comment section under AI answers

---

## 🧪 ACCEPTANCE CRITERIA

- Multiple users can access same workspace
- Shared documents visible across team
- Query threads persist across users
- Comments are visible in real time (or refresh-based)

---
