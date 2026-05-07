# Phase 1.2 – Document Ownership & Storage

## Objective
Manage documents as owned, isolated resources with a scalable and deployment-ready storage model.

## Input
- Uploaded document files (pdf, txt, docx)
- User and collection identifiers

## Output
- Stored documents with unique identifiers
- Ownership and collection metadata

## Functional Requirements
- Each document is associated with exactly one owner
- Documents organized into logical collections (folders)
- File type and size validation
- Persistent metadata storage
- Access restricted to document owner or authorized roles

## Deployment & Infrastructure
- Storage abstraction layer to allow future cloud migration
- Storage root defined via environment variable:
  - STORAGE_PATH
- No absolute or environment-specific file paths
- Compatible with Render filesystem constraints

## Acceptance Criteria
- Users cannot access documents they do not own
- Documents persist across application restarts
- Storage behavior remains consistent after deployment