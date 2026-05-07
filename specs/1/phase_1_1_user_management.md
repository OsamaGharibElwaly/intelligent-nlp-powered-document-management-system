# Phase 1.1 – User Management & Access Control

## Objective
Provide secure user authentication and authorization as the foundation of the management system.

## Input
- User credentials (email, password)
- Authentication requests
- Role assignment (admin, user, viewer)

## Output
- Authenticated user session
- JWT access token
- User role and quota metadata

## Functional Requirements
- JWT-based authentication
- Role-based access control:
  - Admin: full access
  - User: upload and query documents
  - Viewer: read-only access
- Token expiration handling
- Per-user document and storage quotas
- Middleware-based authorization enforcement

## Deployment & Infrastructure
- Authentication module isolated from business logic
- Secrets managed via environment variables:
  - JWT_SECRET
  - TOKEN_EXPIRY
- No hardcoded secrets
- Backend exposes a `/health` endpoint for Render deployment
- Configuration compatible with local and Render environments

## Acceptance Criteria
- Same credentials always produce deterministic authentication results
- Unauthorized requests are rejected based on role
- Authentication works locally and after deployment without code changes