# Phase 1.5 – Audit Logging & Usage History

## Objective
Provide full visibility into user actions and system usage.

## Input
- User actions (upload, query, update, delete, access)

## Output
- Immutable audit log entries
- Per-user usage history

## Functional Requirements
- Log all document uploads and updates
- Log all user queries
- Track last accessed documents per user
- Maintain per-user query history
- Audit logs are append-only

## Deployment & Infrastructure
- Centralized logging module
- Logs written in a format compatible with Render logging
- No reliance on external logging services

## Acceptance Criteria
- Every relevant user action is logged
- Logs remain accessible after deployment
- Logging does not significantly impact system performance