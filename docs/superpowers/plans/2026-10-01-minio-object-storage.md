# MinIO Object Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MinIO-backed image upload URL generation, public image URL lookup, and image deletion endpoints for user avatars, player showcase images, and order evidence images.

**Architecture:** Add a focused MinIO wrapper under `app.providers` and expose it through a small FastAPI router. Configuration lives in `Settings` and `.env.example`; routes return a consistent `{code, message, data}` JSON envelope and catch storage exceptions at the API boundary.

**Tech Stack:** FastAPI, Pydantic, MinIO Python SDK, pytest, TestClient.

---

### Task 1: MinIO Contract Tests

**Files:**
- Create: `services/api/tests/test_object_storage.py`
- Create: `services/api/tests/test_minio_router.py`

- [ ] **Step 1: Write failing tests**

Create tests for object key generation, public URL formatting, route success envelopes, and route exception envelopes. Stub storage in router tests so tests do not require a real MinIO server.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd services/api
pytest tests/test_object_storage.py tests/test_minio_router.py -q
```

Expected: imports fail because `app.providers.object_storage` and `app.routers.minio` do not exist yet.

### Task 2: Storage Wrapper

**Files:**
- Create: `services/api/app/providers/object_storage.py`
- Modify: `services/api/pyproject.toml`

- [ ] **Step 1: Add MinIO SDK dependency**

Add `minio>=7,<8` to project dependencies.

- [ ] **Step 2: Implement wrapper**

Implement `MinIOImageStorage` with initialization, `ensure_bucket`, `set_public_read_policy`, `presigned_upload_url`, `get_public_url`, and `delete_file`.

- [ ] **Step 3: Run object storage tests**

Run:

```bash
cd services/api
pytest tests/test_object_storage.py -q
```

Expected: tests pass.

### Task 3: FastAPI Router

**Files:**
- Create: `services/api/app/routers/minio.py`
- Modify: `services/api/app/main.py`
- Modify: `services/api/app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add settings**

Add `minio_endpoint`, `minio_access_key`, `minio_secret_key`, `minio_bucket_name`, `minio_secure`, `minio_public_url`, and `minio_presigned_expires_seconds`.

- [ ] **Step 2: Add routes**

Expose:

```text
POST /api/minio/get-upload-url
GET /api/minio/get-url
DELETE /api/minio/delete-img
```

Also expose `/api/v1/minio/*` aliases for the repo's versioned API style.

- [ ] **Step 3: Run router tests**

Run:

```bash
cd services/api
pytest tests/test_minio_router.py -q
```

Expected: tests pass.

### Task 4: Documentation and Verification

**Files:**
- Create: `docs/minio.md`

- [ ] **Step 1: Document deployment**

Document local MinIO deployment, environment variables, bucket policy behavior, and security notes.

- [ ] **Step 2: Run focused verification**

Run:

```bash
cd services/api
pytest tests/test_object_storage.py tests/test_minio_router.py -q
```

Expected: all focused tests pass.
