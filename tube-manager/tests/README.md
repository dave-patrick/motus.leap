# Tube Manager - Test Suite

**Status:** Complete
**Coverage:** Unit, Integration, Security, Load Tests

---

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures and setup
├── unit/
│   ├── test_youtube_service.py
│   ├── test_config_manager.py
│   ├── test_cache.py
│   └── test_models.py
├── integration/
│   ├── test_api_endpoints.py
│   ├── test_oauth_flow.py
│   └── test_websocket.py
├── security/
│   ├── test_csp.py
│   ├── test_rate_limiting.py
│   ├── test_xss.py
│   └── test_validation.py
├── load/
│   ├── test_concurrent_requests.py
│   └── test_api_quota.py
└── e2e/
    ├── test_full_scan_flow.py
    └── test_user_journey.py
```

---

## Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Security tests
pytest tests/security/

# Load tests
pytest tests/load/

# With coverage
pytest --cov=. --cov-report=html

# Continuous mode
pytest -f  # Watch mode
```

---

## Coverage Target

- **Minimum:** 80%
- **Target:** 90%
- **Current:** TBD

---

## Test Categories

### Unit Tests
- Test individual functions and classes
- Mock external dependencies
- Fast execution

### Integration Tests
- Test API endpoints
- Test OAuth flow
- Test WebSocket communication
- Use real services where needed

### Security Tests
- Test CSP headers
- Test rate limiting
- Test XSS protection
- Test input validation
- Test authentication/authorization

### Load Tests
- Test concurrent requests
- Test API quota handling
- Test rate limiting under load
- Test WebSocket connection limits

### E2E Tests
- Test complete user flows
- Test UI interactions
- Test background tasks
- Test error scenarios

---

## Test Data

Test data is stored in `tests/fixtures/`:
- Mock YouTube API responses
- Sample playlists
- Test configurations
- Test OAuth tokens

---

## Mock Services

All external services are mocked:
- YouTube API
- OAuth provider
- Database (SQLite in-memory)
- Redis (if used)

---

## CI/CD Integration

Tests run automatically:
- On every pull request
- On every push to main
- Before deployment

---

**Created by:** Hermes Agent
**Date:** 2026-06-13
**Version:** 1.0