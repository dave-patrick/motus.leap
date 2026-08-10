# 📋 Development Roadmap: motus.leap Code Quality & Modernization

## Overview
This roadmap outlines improvements to the motus.leap codebase, organized by priority and effort. The application will remain on Render (no Docker). All other improvements are in scope.

---

## Phase 1: Foundation (High Priority, Low Effort)

### 1. Type Safety & Static Analysis
**Estimated Effort:** 2-3 days

**Tasks:**
- [ ] Add `mypy` with `--strict` mode to `pyproject.toml`
- [ ] Add `ruff` as linter/formatter (replaces flake8, isort, black)
- [ ] Add `pre-commit` hooks for automated checks
- [ ] Add full type annotations to all Python files
- [ ] Fix all mypy errors

**Deliverables:**
- `pyproject.toml` with mypy/ruff/pre-commit config
- Pre-commit hooks installed and configured
- All Python files pass `mypy --strict` and `ruff check`

**Files to modify:** `pyproject.toml`, all `*.py` files

---

### 2. Testing Infrastructure
**Estimated Effort:** 3-5 days

**Tasks:**
- [ ] Add `pytest`, `pytest-asyncio`, `pytest-cov` to dev dependencies
- [ ] Create test directory structure: `tests/unit/`, `tests/integration/`, `tests/e2e/`
- [ ] Write unit tests for core services (`youtube_service.py`, `ai_classifier.py`)
- [ ] Write integration tests for API endpoints
- [ ] Set up test fixtures and conftest.py
- [ ] Configure CI to run tests on every PR

**Deliverables:**
- `tests/` directory with test structure
- `conftest.py` with shared fixtures
- At least 70% code coverage for core modules
- GitHub Actions workflow for test execution

**Files to create:** `tests/`, `tests/conftest.py`, `.github/workflows/test.yml`

---

## Phase 2: Observability & Reliability (High Priority, Medium Effort)

### 3. Observability Stack
**Estimated Effort:** 3-4 days

**Tasks:**
- [ ] Add `structlog` for structured logging (replace `logging`)
- [ ] Add `OpenTelemetry` for distributed tracing
- [ ] Add `Sentry` SDK for error tracking
- [ ] Add health check endpoints (`/health`, `/ready`, `/live`)
- [ ] Add Prometheus metrics endpoint (`/metrics`)
- [ ] Configure Grafana dashboards for key metrics

**Deliverables:**
- Structured JSON logs with trace IDs
- Sentry error tracking configured
- Health check endpoints returning service status
- Prometheus metrics for API latency, error rates, YouTube API usage

**Files to modify:** `app.py`, `core/logger.py`, `core/config_manager.py`
**Files to create:** `core/observability.py`, `core/health.py`

---

### 4. Caching Strategy
**Estimated Effort:** 2-3 days

**Tasks:**
- [ ] Add `Redis` dependency (Render Redis addon)
- [ ] Implement multi-layer caching (Redis + in-memory LRU)
- [ ] Add cache warming for YouTube playlists
- [ ] Implement cache invalidation strategies (TTL, event-based)
- [ ] Add cache hit/miss metrics

**Deliverables:**
- Redis caching layer with TTL
- Cache warming for frequently accessed data
- Metrics for cache performance

**Files to create:** `core/cache.py`, `core/cache_manager.py`
**Files to modify:** `services/youtube_service.py`, `services/youtube_client.py`

---

## Phase 3: Architecture & Infrastructure (Medium Priority, Medium Effort)

### 5. Database Layer Modernization
**Estimated Effort:** 3-4 days

**Tasks:**
- [ ] Migrate from raw SQLite to `SQLAlchemy 2.0` with async support
- [ ] Add `alembic` for database migrations
- [ ] Implement connection pooling
- [ ] Add database health checks
- [ ] Create ORM models for all entities

**Deliverables:**
- SQLAlchemy models for all database tables
- Alembic migration scripts
- Connection pooling configured
- Database health check endpoint

**Files to create:** `models/`, `migrations/`, `core/database.py`
**Files to modify:** `services/db.py`, all files using SQLite directly

---

### 6. Background Task Processing
**Estimated Effort:** 2-3 days

**Tasks:**
- [ ] Evaluate `Celery` vs `Dramatiq` for task queue
- [ ] Set up task queue with Redis broker
- [ ] Migrate existing background worker to task queue
- [ ] Add task monitoring (Flower or custom dashboard)
- [ ] Implement task retry policies and rate limiting

**Deliverables:**
- Task queue infrastructure
- Migrated background tasks
- Task monitoring dashboard

**Files to create:** `core/tasks.py`, `core/task_queue.py`
**Files to modify:** `services/background_worker.py`

---

### 7. Configuration Management
**Estimated Effort:** 1-2 days

**Tasks:**
- [ ] Migrate from JSON config to `Pydantic Settings`
- [ ] Add environment-based configuration
- [ ] Add feature flags support
- [ ] Add config validation and defaults

**Deliverables:**
- Pydantic settings model
- Environment variable configuration
- Feature flags for experimental features

**Files to create:** `core/settings.py`
**Files to modify:** `core/config_manager.py`

---

## Phase 4: Frontend Modernization (Medium Priority, High Effort)

### 8. Frontend Architecture
**Estimated Effort:** 5-7 days

**Tasks:**
- [ ] Set up React + TypeScript + Vite
- [ ] Create component library with Tailwind CSS
- [ ] Implement state management (Zustand or Pinia)
- [ ] Migrate existing pages to React components
- [ ] Add proper routing and navigation
- [ ] Implement proper error boundaries

**Deliverables:**
- React + TypeScript frontend
- Component library
- State management
- Migrated UI pages

**Files to create:** `frontend/src/`
**Files to modify:** `web/*.html`, `web/static/*.js`

---

## Phase 5: Security & API Improvements (Low Priority, Medium Effort)

### 9. Security Enhancements
**Estimated Effort:** 2-3 days

**Tasks:**
- [ ] Add `bandit` for security linting
- [ ] Add `safety`/`pip-audit` for dependency scanning
- [ ] Add `semgrep` for code analysis
- [ ] Implement audit logging for sensitive operations
- [ ] Add security headers middleware
- [ ] Add input validation and sanitization

**Deliverables:**
- Security scanning in CI pipeline
- Audit logs for admin operations
- Security headers configured

**Files to modify:** `app.py`, `.github/workflows/security.yml`

---

### 10. API Improvements
**Estimated Effort:** 2-3 days

**Tasks:**
- [ ] Add API versioning (`/api/v1/`, `/api/v2/`)
- [ ] Add GraphQL endpoint for flexible queries
- [ ] Add request/response compression
- [ ] Add API rate limiting per endpoint
- [ ] Improve OpenAPI documentation

**Deliverables:**
- Versioned API endpoints
- GraphQL endpoint
- Compressed responses
- Improved API docs

**Files to modify:** `app.py`, `api/*.py`
**Files to create:** `api/graphql.py`

---

## Phase 6: Documentation & Maintenance

### 11. Documentation
**Estimated Effort:** 2-3 days

**Tasks:**
- [ ] Set up `MkDocs` for project documentation
- [ ] Write architecture documentation
- [ ] Write API documentation
- [ ] Write deployment and maintenance guides
- [ ] Add architecture decision records (ADRs)

**Deliverables:**
- Project documentation site
- Architecture diagrams
- Deployment guide
- ADRs for major decisions

**Files to create:** `docs/`, `docs/adr/`

---

## 📊 Priority Matrix

| Task | Priority | Effort | Impact | Dependencies |
|------|----------|--------|--------|--------------|
| Type Safety & Static Analysis | 🔴 High | Low | High | None |
| Testing Infrastructure | 🔴 High | Medium | High | None |
| Observability Stack | 🔴 High | Medium | High | None |
| Caching Strategy | 🟠 Medium | Medium | Medium | Redis |
| Database Layer | 🟠 Medium | Medium | Medium | None |
| Background Tasks | 🟠 Medium | Medium | Medium | Redis |
| Frontend Modernization | 🟡 Low | High | Medium | None |
| Security Enhancements | 🟡 Low | Medium | Medium | None |
| API Improvements | 🟡 Low | Medium | Medium | None |
| Documentation | 🟢 Low | Medium | Low | None |

---

## 🛠️ Technical Stack Summary

| Category | Current | Target |
|----------|---------|--------|
| **Language** | Python 3.12 | Python 3.12 |
| **Framework** | FastAPI | FastAPI |
| **Database** | SQLite (raw) | SQLAlchemy 2.0 + Alembic |
| **Caching** | Disk-based | Redis + LRU |
| **Logging** | logging | structlog |
| **Monitoring** | Basic logs | OpenTelemetry + Sentry + Prometheus |
| **Testing** | None | pytest + pytest-asyncio |
| **Linting** | None | ruff + mypy + pre-commit |
| **Frontend** | Vanilla JS | React + TypeScript + Vite |
| **CI/CD** | Render auto-deploy | GitHub Actions |
| **Deployment** | Render | Render (unchanged) |

---

## 📝 Implementation Notes

1. **Backward Compatibility:** All changes should maintain backward compatibility with existing API endpoints and data formats.
2. **Incremental Deployment:** Each phase should be deployable independently.
3. **Testing:** Each phase should include appropriate tests.
4. **Documentation:** Each phase should update relevant documentation.
5. **Render:** No Docker changes needed - continue using Render's Python buildpack.

---

## 🚀 Getting Started

1. **Start with Phase 1** (Type Safety & Testing) - these provide immediate value with low risk
2. **Set up CI/CD** early to catch issues automatically
3. **Add observability** before making major architectural changes
4. **Frontend modernization** can be done in parallel with backend improvements
5. **Database migration** should be done carefully with proper migration scripts

---

## ✅ Completed Fixes (Already Applied)

| Commit | Fix | Status |
|--------|-----|--------|
| `d0974ae` | Import `timezone` in `youtube_service.py` | ✅ Applied |
| `aa5a6f4` | Background worker sleep: 10ms → 0.5s | ✅ Applied |
| `d8567a3` | `_classify_sync` → `_classify_async` | ✅ Applied |
| `fe352c3` | `_retry_on_ssl` → `_retry_on_ssl_async` | ✅ Applied |
| `cd23626` | `_with_retry` → `_with_retry_async` + cleanup | ✅ Applied |
| `74125b4` | Settle delay: 10s → 2s | ✅ Applied |
| `7aecd7a` | YouTube quota notification banner | ✅ Applied |
| `e9c6462` | AI discovery probe retry with backoff | ✅ Applied |
| `6a94b1f` | Mobile touch targets, dvh heights | ✅ Applied |
| `93b78c9` | UI body placement, alt attrs, focus | ✅ Applied |
| `8df2c1f` | Randomize admin password, sanitize innerHTML | ✅ Applied |
| `9202ae0` | `orjson` added to requirements.txt | ✅ Applied |
