# Security Audit Report - Tube Manager

**Date:** 2026-06-13
**Scope:** Full application security assessment
**Status:** 🟡 Medium Risk - Several vulnerabilities found
**Priority:** High

---

## 📊 Executive Summary

**Total Vulnerabilities:** 8
- **Critical:** 0
- **High:** 2
- **Medium:** 4
- **Low:** 2

**Overall Risk Level:** MEDIUM

---

## 🔴 Critical Vulnerabilities

*None found*

---

## 🟠 High Severity Vulnerabilities

### 1. Weak Content Security Policy (CSP) - `unsafe-inline` and `unsafe-eval`

**Location:** `tube-manager/app.py:148-162`

**Vulnerability:**
```python
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
    "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
    "img-src 'self' data: https:; "
    "connect-src 'self' wss: https:; "
    "frame-ancestors 'self'; "
    "frame-src 'self' https:;"
)
```

**Issues:**
1. **`'unsafe-inline'`** allows inline scripts and styles - defeats CSP purpose
2. **`'unsafe-eval'`** allows `eval()` and similar functions - XSS risk
3. **No nonces or hashes** - can't verify script authenticity
4. **`data:` in `img-src`** - allows data URIs (potential XSS vector)
5. **`https:` in `connect-src`** - allows connections to ANY HTTPS site

**Risk:** Cross-Site Scripting (XSS) attacks could inject malicious scripts

**Affected Files:**
- `tube-manager/app.py` (middleware)
- All HTML files (meta tags)

**Impact:** HIGH
- If attacker can inject content, they can execute arbitrary JavaScript
- Compromise user sessions, OAuth tokens, API keys

---

### 2. Missing Rate Limiting on API Endpoints

**Location:** All FastAPI endpoints (`/api/*`)

**Vulnerability:**
- No rate limiting implemented
- WebSocket throttles but HTTP endpoints don't
- Can be abused for:
  - API quota exhaustion
  - DDoS attacks
  - Brute force on OAuth endpoints

**Issues:**
```python
@app.get("/api/youtube/fetch-all")  # No rate limit
async def fetch_all_youtube_data(force_refresh: bool = False):
    # Direct call to YouTube API - can be abused
```

**Risk:**
- Attacker can consume all YouTube API quota
- Denial of Service via repeated requests
- OAuth callback abuse

**Impact:** HIGH
- Service disruption
- API quota exhaustion
- Potential cost overage

---

## 🟡 Medium Severity Vulnerabilities

### 3. `innerHTML` Usage Without Sanitization

**Location:** All HTML files (dashboard, playlists, subscriptions, etc.)

**Vulnerability:**
```javascript
// In dashboard.html
el.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span>${message}</span>`;
terminal.innerHTML += `\n[${time}] ${message}`;
content.innerHTML = scanLogs.slice().reverse().map(log => `<div class="scan-entry ${log.type}">...</div>`).join('');
```

**Issues:**
- Direct use of `innerHTML` with user data
- No HTML sanitization before injection
- Even with `escapeHtml()`, bypasses possible via Unicode tricks
- Combined with `unsafe-inline` CSP, XSS is possible

**Risk:** XSS via WebSocket messages or API responses

**Impact:** MEDIUM
- Attacker can inject scripts via WebSocket messages
- If API responses contain malicious data, it gets executed
- Only mitigated by WebSocket message format (not user input directly)

---

### 4. Missing Security Headers

**Location:** `tube-manager/app.py`

**Vulnerability:**
- No `X-Frame-Options` header (clickjacking protection)
- No `Strict-Transport-Security` header (HSTS)
- No `X-Content-Type-Options: nosniff` header
- No `X-XSS-Protection` header (deprecated but helps older browsers)
- No `Referrer-Policy` header
- No `Permissions-Policy` header

**Current:** Only CSP header set

**Impact:** MEDIUM
- Clickjacking attacks possible
- No HTTPS enforcement
- MIME type sniffing enabled

---

### 5. Sensitive Data in Logs

**Location:** `tube-manager/app.py:738-739`

**Vulnerability:**
```python
log.info(f"Token response keys: {list(tokens.keys())}")
log.info("YouTube OAuth tokens saved successfully")
```

**Issues:**
- Logging OAuth token keys
- Could accidentally log tokens in debug mode
- Log files might be accessible

**Risk:** OAuth tokens exposed in logs

**Impact:** MEDIUM
- If logs are compromised, tokens could be leaked
- Debug logs might include sensitive data

---

### 6. No Input Validation on API Endpoints

**Location:** FastAPI endpoints (`/api/*`)

**Vulnerability:**
```python
@app.get("/api/youtube/fetch-all")
async def fetch_all_youtube_data(force_refresh: bool = False):
    # force_refresh not validated
    result = await youtube_service.fetch_all_data(force_refresh=force_refresh)

@app.post("/api/mappings")
async def save_mappings(body: dict[str, Any]):
    # No validation on body structure
    mappings = _normalize_mappings(_extract_mappings_items(body))
```

**Issues:**
- `force_refresh` accepts any boolean (should be rate-limited)
- `body` accepts any dict structure
- No schema validation
- No length limits

**Risk:** API abuse, DoS via large payloads

**Impact:** MEDIUM
- Large payloads could consume memory
- Malformed data could cause errors

---

## 🟢 Low Severity Vulnerabilities

### 7. Backup Files in Repository

**Location:** Multiple `.py` backup files

**Vulnerability:**
```
app_backup_before_refactor_20260612_231527.py
app_old.py
```

**Issues:**
- Old code with potential vulnerabilities
- May contain secrets or deprecated logic
- Bloats repository size
- Confusion about which file is current

**Risk:** Security researchers might find vulnerabilities in old code

**Impact:** LOW
- Information disclosure
- Potential confusion

---

### 8. Debug/Development Comments in Code

**Location:** Multiple files

**Vulnerability:**
```python
# TODO: Is this the correct definition according to the DB API 2 Spec?
# Simulate clustering analysis (could be replaced with real ML later)
```

**Issues:**
- TODOs and comments indicate incomplete features
- May give attackers clues about architecture
- No security impact, just information disclosure

**Impact:** LOW
- Information disclosure

---

## 🔍 Additional Security Issues

### Good Practices Found ✅

1. **Secrets properly managed** - Using Pydantic `SecretStr` for API keys
2. **OAuth tokens masked** - Tokens displayed with `••••`
3. **HTTPS only for OAuth** - Redirect URIs use HTTPS
4. **WebSocket throttling** - 100ms minimum interval per client
5. **LRU cache with TTL** - Prevents unbounded memory growth
6. **Pagination caps** - Prevents API quota exhaustion
7. **Connection pooling** - HTTP/2 with connection reuse
8. **.gitignore properly configured** - `.env` files excluded
9. **No hardcoded secrets** - All credentials in environment/config

---

## 📋 Missing Security Features

1. **Rate limiting** - Not implemented on HTTP endpoints
2. **CORS configuration** - Not explicitly set (uses FastAPI defaults)
3. **CSRF protection** - Not implemented (stateless API, but good to note)
4. **Request ID tracking** - Not implemented
5. **Security audit logging** - Not implemented
6. **Input sanitization** - No HTML sanitization library
7. **Dependency vulnerability scanning** - Not automated
8. **Secrets rotation** - Not implemented
9. **API key rotation** - Not implemented

---

## 🎯 Remediation Priorities

### Priority 1 (Immediate - High Severity)

1. **Remove `unsafe-inline` and `unsafe-eval` from CSP**
   - Replace with nonces or hashes
   - Remove `data:` from `img-src`
   - Restrict `connect-src` to specific domains

2. **Implement rate limiting**
   - Use `slowapi` or `fastapi-limiter`
   - Rate limit all `/api/*` endpoints
   - Rate limit OAuth callback

---

### Priority 2 (Soon - Medium Severity)

3. **Sanitize HTML before `innerHTML`**
   - Use `DOMPurify` or similar library
   - Escape all user-provided content
   - Use `textContent` instead of `innerHTML` where possible

4. **Add security headers**
   - `X-Frame-Options: DENY` or `SAMEORIGIN`
   - `Strict-Transport-Security: max-age=31536000`
   - `X-Content-Type-Options: nosniff`
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `Permissions-Policy`

5. **Review logging** - Remove sensitive data from logs
6. **Add input validation** - Validate all API request bodies

---

### Priority 3 (Nice to Have - Low Severity)

7. **Remove backup files** from repository
8. **Clean up debug comments**
9. **Implement CORS configuration**
10. **Add request ID tracking**

---

## 📊 Compliance Check

| Standard | Compliant | Notes |
|----------|-----------|-------|
| OWASP Top 10 | ❌ No | Missing XSS protection, rate limiting |
| CSP Level 3 | ❌ No | `unsafe-inline` not allowed |
| HSTS | ❌ No | Header not set |
| HTTPS Only | ✅ Yes | All external URLs use HTTPS |
| OAuth 2.0 Best Practices | ✅ Yes | Proper token handling, PKCE could be added |

---

## 🔐 Detailed Findings

### Finding 1: CSP Bypass via `unsafe-inline`

**CVSS Score:** 7.5 (High)
**CWE:** CWE-79 (Cross-site Scripting)

**Proof of Concept:**
```javascript
// If attacker can inject message via WebSocket:
// message: "<script>alert('XSS')</script>"
el.innerHTML = `<i class="fa-solid ${icons[type]}"></i><span>${message}</span>`;
// Will execute if CSP allows unsafe-inline
```

**Fix:**
```python
# Generate nonce for each request
import secrets

@app.middleware("http")
async def add_csp_header(request: Request, call_next):
    nonce = secrets.token_hex(16)
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        f"default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' https://cdn.tailwindcss.com; "
        f"style-src 'self' 'nonce-{nonce}' https://fonts.googleapis.com; "
        f"img-src 'self' https://i.ytimg.com https://yt3.ggpht.com; "
        f"connect-src 'self' https://www.googleapis.com https://www.youtube.com wss:; "
        f"frame-ancestors 'none'; "
        f"frame-src 'none';"
    )
    # Add nonce to response context
    response.headers["X-CSP-Nonce"] = nonce
    return response
```

---

### Finding 2: No Rate Limiting

**CVSS Score:** 6.5 (Medium)
**CWE:** CWE-770 (Allocation of Resources Without Limits)

**Proof of Concept:**
```bash
# Attacker can exhaust API quota
for i in {1..1000}; do
  curl "https://tubemanager.onrender.com/api/youtube/fetch-all?force_refresh=true" &
done
```

**Fix:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/youtube/fetch-all")
@limiter.limit("10/minute")  # 10 requests per minute
async def fetch_all_youtube_data(
    request: Request,
    force_refresh: bool = False
):
    result = await youtube_service.fetch_all_data(force_refresh=force_refresh)
    return result
```

---

## 📝 Recommendations

### Immediate Actions

1. **Fix CSP** - Remove `unsafe-inline` and `unsafe-eval`
2. **Add rate limiting** - Implement on all API endpoints
3. **Review code** - Remove `innerHTML` usage or sanitize input
4. **Add security headers** - Implement all recommended headers

### Short-term Actions

1. **Input validation** - Add Pydantic models for all API inputs
2. **Logging audit** - Remove sensitive data from logs
3. **Dependencies** - Run `pip-audit` to check for vulnerabilities
4. **CORS** - Configure explicit CORS settings

### Long-term Actions

1. **HSTS** - Enable HTTP Strict Transport Security
2. **CSRF** - Consider CSRF tokens for state-changing operations
3. **Audit logging** - Log security-relevant events
4. **Secrets rotation** - Implement automated rotation

---

## 🧪 Testing Recommendations

1. **XSS Testing**
   - Inject `<script>alert('XSS')</script>` via WebSocket
   - Try Unicode-based XSS bypasses
   - Test with DOMPurify disabled

2. **Rate Limit Testing**
   - Send 100+ requests in 1 minute
   - Test with different IP addresses
   - Test OAuth callback rate limiting

3. **CSP Testing**
   - Use CSP Evaluator tool
   - Test nonce/hash implementation
   - Verify no inline scripts execute

4. **Header Testing**
   - Check security headers with `curl -I`
   - Use securityheaders.com
   - Test with OWASP ZAP

---

## 📚 Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CSP Evaluator](https://csp-evaluator.withgoogle.com/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Rate Limiting with SlowAPI](https://github.com/laurentS/slowapi)

---

## 🏆 Summary

**Security Status:** 🟡 MEDIUM RISK

**Strengths:**
- ✅ Proper secrets management
- ✅ HTTPS enforcement for OAuth
- ✅ WebSocket throttling
- ✅ LRU cache with eviction
- ✅ Pagination caps

**Weaknesses:**
- ❌ Weak CSP (`unsafe-inline`, `unsafe-eval`)
- ❌ No rate limiting on HTTP endpoints
- ❌ `innerHTML` usage without sanitization
- ❌ Missing security headers

**Action Required:**
- 2 HIGH severity issues need immediate attention
- 4 MEDIUM severity issues should be addressed soon
- 2 LOW severity issues can be addressed later

**Estimated Remediation Time:** 4-6 hours for Priority 1 fixes

---

**Audited by:** Hermes Agent
**Date:** 2026-06-13
**Next Review:** After Priority 1 fixes implemented
**Version:** 1.0