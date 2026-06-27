# 🔒 SECURITY AUDIT REPORT — motus.leap

**Auditor**: jnu (security-focused coder)  
**Date**: 2026-06-27  
**Scope**: Authentication, Authorization, Input Validation, Injection, Secrets, CORS/CSRF, Rate Limiting, Session Management, Headers & Transport  
**Project**: `/opt/data/motus.leap/tube-manager/`  

---

## Executive Summary

motus.leap is a reasonably well-architected application with several security measures in place (CSP headers, password in responses). However, this audit identified **4 CRITICAL**, **6 HIGH**, **5 MEDIUM**, and **6 LOW** severity findings that collectively expose the application to unauthorized data access, unauthenticated state-changing operations, SSRF, and missing transport security.

---

## 1. Authentication & Authorization

### 1.1 � CRITICAL: Multiple Unprotected State-Changing Endpoints

Several sensitive endpoints lack authentication entirely. An unauthenticated attacker can:
- Read full settings (including API key prefix, OAuth client ID)
- Scan YouTube data (duplicates, misplaced videos)
- Read AI training memory
- Access diagnostics endpoints

| Endpoint | Method | Auth Present? | Impact |
|----------|--------|---------------|--------|
| `/api/watch-later` | POST (`watch_later_sync`) | ❌ None | Unauth access to Watch Later |
| `/api/settings` | GET | ❌ None | Settings exposed (client_id, API key prefix) |
| `/api/youtube/duplicates` | GET | ❌ None | Read YouTube scan data |
| `/api/youtube/misplaced` | GET | ❌ None | Read YouTube scan data |
| `/api/ai/suggestions` | GET | ❌ None | Read AI training patterns |
| `/api/ai/memory` | GET | ❌ None | Expose AI memory (video titles, emails in usernames) |
| `/api/diagnostics/youtube` | GET | ❌ None | Full YouTube diagnostics |
| `/api/diagnostics/oauth-user` | GET | ❌ None | Email/name enumeration |
| `/api/system/logs` | GET | ❌ None | System information disclosure |
| `/api/maintenance` | GET | ❌ None | Read maintenance data |

**Exploitability**: EASY — Direct HTTP requests, no authentication needed  
**Suggested Fix**:
```python
# app.py — Add auth to ALL unauthenticated sensitive endpoints
@app.get("/api/settings", dependencies=[Depends(get_current_user)])
async def get_settings():
    ...

@app.get("/api/youtube/duplicates", dependencies=[Depends(get_current_user)])
async def scan_duplicates_endpoint(playlist_id: Optional[str] = None):
    ...

@app.get("/api/youtube/misplaced", dependencies=[Depends(get_current_user)])
async def scan_misplaced_endpoint(playlist_id: Optional[str] = None):
    ...

@app.get("/api/ai/suggestions", dependencies=[Depends(get_current_user)])
async def ai_get_suggestions():
    ...

@app.get("/api/ai/memory", dependencies=[Depends(get_current_user)])
async def ai_get_memory():
    ...

@app.get("/api/diagnostics/youtube", dependencies=[Depends(get_current_user)])
async def diagnostics_youtube():
    ...

@app.get("/api/diagnostics/oauth-user", dependencies=[Depends(get_current_user)])
async def diagnostics_oauth_user():
    ...

@app.get("/api/system/logs", dependencies=[Depends(get_current_user)])
async def get_system_logs():
    ...

@app.get("/api/maintenance", dependencies=[Depends(get_current_user)])
async def api_maintenance():
    ...

@app.post("/api/watch-later", dependencies=[Depends(get_current_user)])
async def watch_later_sync(body: dict):
    ...
```

---

### 1.2 🔴 CRITICAL: WebSocket Endpoint Has No Authentication

```python
# app.py line 1691
@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    await manager.connect(websocket)  # No auth check!
```

The `/ws/terminal` endpoint accepts WebSocket connections with **zero authentication**. Anyone can connect and receive broadcast messages (including task logs, system events). The `dashboard.js` sends the JWT as a query parameter (`?token=...`), but the server never validates it.

**Exploitability**: EASY — Open WebSocket connection from any origin  
**Suggested Fix**:
```python
@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    # Reject connections without valid token
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        if not username:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return
    await manager.connect(websocket)
```

---

### 1.3 🟠 HIGH: CSRF/Origin Bypass via Permissive `verify_origin`

```python
# auth.py lines 216-220
if ".onrender.com" in origin:  # ← Allows ANY subdomain
    return
if "localhost" in origin or "127.0.0.1" in origin:  # ← Allows any port/path
    return
```

The string-contains check is bypassable:
- Attacker controls `https://evil.onrender.com` → passes (if deploying on Render)
- Attacker controls `https://tubemanager.onrender.com.evil.com` → passes
- Any page on `http://localhost:9999/path` → passes
- Any referer containing "localhost" → passes (XSS on any local site)

Additionally, when **no Origin AND no Referer** headers are present, the request passes through:
```python
# auth.py line 231-233
# No origin and no referer — likely Render health check or internal call. Allow through.
log.debug("verify_origin: ALLOWED (no origin/referer)")
return
```

This means any tool that strips Origin/Referer headers (e.g., direct HTTP requests, curl, scripts) bypasses CSRF protection completely.

**Exploitability**: MEDIUM — Requires finding a matching subdomain or stripping headers  
**Suggested Fix**:
```python
from urllib.parse import urlparse

ALLOWED_ORIGINS = {
    "https://tubemanager.onrender.com",
    "https://motus-leap.onrender.com",
    "http://localhost:8000",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:3000",
}

def verify_origin(request: Request):
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    
    # Check origin against allowlist (exact match)
    if origin and origin in ALLOWED_ORIGINS:
        return
    
    # Check referer origin component
    if referer:
        parsed = urlparse(referer)
        referer_origin = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port and parsed.port not in (80, 443):
            referer_origin += f":{parsed.port}"
        if referer_origin in ALLOWED_ORIGINS:
            return
    
    # For API calls with no origin/referer, require valid auth token
    # (they'll be checked by get_current_user dependency)
    # But CSRF protection needs the origin check for browser requests
    if not origin and not referer:
        # Allow server-to-server (health checks) but block browser-based attacks
        auth_header = request.headers.get("authorization", "")
        if not auth_header:
            raise HTTPException(status_code=403, detail="Forbidden: Missing origin")
        return
    
    raise HTTPException(status_code=403, detail="Forbidden: Invalid origin")
```

---

### 1.4 � HIGH: Weak Default Admin Password

```python
# auth.py line 791
default_password = os.getenv("TUBE_MANAGER_ADMIN_PASSWORD", "admin")
```

The default admin password is the string `"admin"`. The warning is only logged at startup and visible in server logs. Anyone who deploys without setting `TUBE_MANAGER_ADMIN_PASSWORD` has a publicly known admin credential. Combined with the `/register` endpoint having a rate limit of only 5/minute, brute-force trivial.

**Exploitability**: EASY (if default not changed)  
**Suggested Fix**: Require a non-default password or refuse to start with a weak default. Use a generated password printed on first boot.

---

### 1.5 � HIGH: `config.json` Stores Plaintext Secrets on Disk

```json
{
  "youtube_api_key": "test_key",
  "oauth": {
    "client_id": "test_id",
    "client_secret": "test_secret",
    "access_token": null,
    "refresh_token": null
  }
}
```

The `to_dict_for_storage()` method in `models/config.py` extracts SecretStr values to plaintext:
```python
data['oauth']['client_secret'] = _secret(self.oauth.client_secret)
data['youtube_api_key'] = _secret(self.youtube_api_key)
data['ai_api_key'] = _secret(self.ai_api_key)
```

These are written directly to `config.json`. While `SecretStr` protects against accidental logging in memory, **all secrets are persisted in plaintext on disk**.

**Exploitability**: MEDIUM — Requires file system access  
**Suggested Fix**: Use environment variables or a secrets manager. If file storage is necessary, encrypt at rest with a key derived from an environment variable.

---

### 1.6 🟡 MEDIUM: No Token Revocation List / Deny List

Tokens are stored in `user_sessions.json` and removed on logout, but there is no centralized deny list. If a user changes their password (via password reset), existing tokens remain valid until they expire (7 days).

**Exploitability**: DIFFICULT  
**Suggested Fix**: Add a `password_version` field to users. Include it in the JWT claims. On password reset, increment the version. Reject tokens with stale versions.

---

### 1.7 🟡 MEDIUM: Cookie `Secure` Flag Depends on `ENV` Variable

```python
# auth.py line 547
secure=os.getenv("ENV") == "production"
```

If the `ENV` variable is not set (or misspelled), cookies will be sent over plain HTTP. The default case should be `True`.

**Exploitability**: MEDIUM — Requires misconfiguration  
**Suggested Fix**:
```python
secure=os.getenv("ENV", "production").lower() in ("production", "prod", "true")
# Or better: always True when HTTPS is detected
```

---

## 2. Input Validation

### 2.1 🔴 CRITICAL: No Video ID Validation (YouTube ID Injection)

Video IDs are passed directly to YouTube API calls with zero validation:
```python
# api/bulk_operations_impl.py line 100-112
"playlistId": target_playlist_id,
"resourceId": {
    "kind": "youtube#video",
    "videoId": video_id  # ← User input, no validation
}
```

While the YouTube API will reject invalid IDs (returning 400), error messages from the API could leak internal data to the caller.

**Exploitability**: EASY  
**Suggested Fix**:
```python
import re

YOUTUBE_VIDEO_ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]{11}$')
YOUTUBE_PLAYLIST_ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]+$|^WL$|^FL[A-Za-z0-9_-]+$|^UU[A-Za-z0-9_-]+$')
YOUTUBE_CHANNEL_ID_PATTERN = re.compile(r'^UC[A-Za-z0-9_-]{22}$')

def validate_video_id(video_id: str) -> bool:
    return bool(YOUTUBE_VIDEO_ID_PATTERN.match(video_id))

def validate_playlist_id(pl_id: str) -> bool:
    return bool(YOUTUBE_PLAYLIST_ID_PATTERN.match(pl_id))

# Apply in the BulkMoveRequest model validator
@validator('video_ids', each_item=True)
def validate_video_ids(cls, v):
    if not YOUTUBE_VIDEO_ID_PATTERN.match(v):
        raise ValueError(f"Invalid video ID format: {v}")
    return v
```

---

### 2.2 🟠 HIGH: No Max Length on Bulk Operation Payloads

`BulkMoveRequest.video_ids` and `BulkTagRequest.video_ids` accept unlimited lists:
```python
class BulkMoveRequest(BaseModel):
    video_ids: List[str]  # ← No max length
    target_playlist_id: str
```

An attacker could submit a million-item list, exhausting memory/API quota.

**Exploitability**: EASY  
**Suggested Fix**:
```python
from pydantic import Field, validator

class BulkMoveRequest(BaseModel):
    video_ids: List[str] = Field(..., max_items=500)
    target_playlist_id: str
    source_playlist_id: Optional[str] = None
```

---

### 2.3 � HIGH: User Registration Has No Validation on `username`

```python
class UserCreate(BaseModel):
    username: str  # ← No min/max length, no character restrictions
```

Attacker could register with:
- Empty string (after strip)
- Username containing `../` (path traversal in logs)
- Username of "admin" with different casing
- Extremely long string (DoS)

**Exploitability**: EASY  
**Suggested Fix**:
```python
from pydantic import Field, validator
import re

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, regex=r'^[a-zA-Z0-9_]+$')
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=100)
    
    @validator('username')
    def username_not_reserved(cls, v):
        reserved = {'admin', 'administrator', 'system', 'root', 'api', 'null'}
        if v.lower() in reserved:
            raise ValueError(f'Username "{v}" is reserved')
        return v
```

---

### 2.4 🟡 MEDIUM: `ai_custom_endpoint` Not Validated as URL (SSRF Vector in AI Classifier)

```python
# ai_classifier.py line 271
url = endpoint.rstrip("/") + "/chat/completions"
resp = httpx.post(url, ...)
```

While only authenticated users can trigger this (via Classification), the endpoint accepts arbitrary URLs. Combined with the fact that `/api/ai/classify` requires only auth (not even admin), any authenticated user can probe internal services.

**Exploitability**: MEDIUM (requires valid user account)  
**Suggested Fix**:
```python
from urllib.parse import urlparse

BLOCKED_NETWORKS = {'10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '127.0.0.0/8', '169.254.0.0/16'}

def validate_custom_endpoint(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    if parsed.scheme not in ('http', 'https'):
        return False
    # Check for SSRF to internal networks
    import ipaddress
    import socket
    try:
        ip = socket.gethostbyname(parsed.hostname)
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return False
    except socket.gaierror:
        return False
    return True
```

---

## 3. Injection Attacks

### 3.1 � HIGH: SSRF in Webhook Test Endpoint

```python
# app.py lines 1674-1687
@app.post("/api/webhook/test", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def test_webhook(body: dict):
    url = body.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL required")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json={"test": True, "source": "motus.leap"})
```

Any authenticated user can request the server to make HTTP POST requests to **any URL**, including internal services (AWS metadata at `169.254.169.254`, Docker socket, etc.).

**Exploitability**: EASY (only needs auth)  
**Suggested Fix**:
```python
import ipaddress
from urllib.parse import urlparse

def validate_webhook_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False
    # Resolve hostname and check for private IPs
    import socket
    try:
        ip = socket.gethostbyname(parsed.hostname)
        addr = ipaddress.ip_address(ip)
        return not (addr.is_private or addr.is_loopback or addr.is_link_local)
    except socket.gaierror:
        return False

# In endpoint:
if not validate_webhook_url(url):
    raise HTTPException(status_code=400, detail="URL not allowed (internal addresses blocked)")
```

---

### 3.2 🟠 HIGH: Server Accessible via Cookie File Path

```python
# app.py lines 1559-1563
cookies_file = Path(__file__).resolve().parent / "data" / "youtube_cookies.json"
```

This path is hardcoded. The file is written without any sanitization of the cookie data itself. The `_sanitize_cookies()` function only checks structural fields, not value integrity.

---

### 3.3 � MEDIUM: HTML in OAuth Callback Response (XSS)

```python
# auth.py lines 929-932
error_msg = tokens.get("error_description", tokens.get("error", str(tokens)))
return HTMLResponse(f"""
    <h1 style="color: #ff4444;">❌ OAuth Error</h1>
    <p><strong>Error:</strong> {error_msg}</p>
""", status_code=400)
```

The `error_description` and `error` values from Google's OAuth response are inserted directly into HTML without escaping. If an attacker can manipulate the OAuth callback (e.g., by crafting a malicious `error_description` parameter), this enables reflected XSS.

**Exploitability**: MEDIUM (requires user interaction with crafted OAuth URL)  
**Suggested Fix**:
```python
from html import escape
error_msg = escape(str(tokens.get("error_description", tokens.get("error", str(tokens)))))
```

---

### 3.4 🟢 LOW: Config.json Contains XSS Test Payload

```json
{
  "channel_mappings": {
    "<script>alert('XSS')</script>": "playlist1"
  }
}
```

This key in `config.json` will be stored and passed to the YouTube API, causing unexpected behavior. While YouTube APIs reject invalid channel IDs, the string could appear in logs/error messages unescaped.

---

## 4. Secrets & Credentials

### 4.1 � MEDIUM: Logging Statements Could Leak Sensitive Patterns

```python
# youtube_service.py line 174
log.debug(f"[YOUTUBE] _oauth_request GET {url} params={params}")
```

While the access_token is in the Authorization header (not URL/params), the debug logs for OAuth requests could still expose internal API structure. The `_redact_secrets()` function exists but is only applied to the `raw_api_response` in diagnostics, not to all log outputs.

**Suggested Fix**: Audit all `log.*` calls with token-adjacent data. Ensure `_redact_secrets()` is applied universally before any caching or logging.

---

### 4.2 🟡 MEDIUM: `videos()` Endpoint Exposes User Email in Cache Key

```python
# app.py lines 770-771
user_id = hashlib.sha256((config.oauth.access_token or "").encode()).hexdigest()[:16]
```

While hashed, this creates a reversible mapping if the config.json is accessible. The access token itself is used to derive a persistent identifier.

---

### 4.3 🟢 LOW: Default Admin Password Logged at Startup

```python
# auth.py line 794
log.warning("Using default admin password 'admin'. Set TUBE_MANAGER_ADMIN_PASSWORD env var to change.")
```

This warning confirms the password value in logs, which may be accessible to operators without providing actionable guidance.

---

## 5. CORS & CSRF

### 5.1 � MEDIUM: CORS Allowlist Has Issues

```python
# app.py lines 228-237
allow_origins=[
    _render_url,
    "https://motus-leap.onrender.com",
    "http://localhost:8000",
    ...
] + [o.strip() for o in _extra_origins if o.strip()],
allow_credentials=True,  # ← Allows cookies
allow_methods=["*"],
allow_headers=["*"],
```

Issues:
1. `allow_credentials=True` + dynamic origins from env = potential misconfiguration
2. `allow_headers=["*"]` means any custom header is allowed
3. `EXTRA_ALLOWED_ORIGINS` env var is comma-separated — if empty string, it adds `""` (empty origin = `file://` schemes)

**Exploitability**: MEDIUM  
**Suggested Fix**:
```python
# Never allow credentials with wildcard/dynamic origins
allow_origins = [o.strip() for o in set([_render_url, "https://motus-leap.onrender.com", 
                   "http://localhost:8000"]) if o and o.strip()]
extra = os.environ.get("EXTRA_ALLOWED_ORIGINS", "")
if extra:
    allow_origins.extend(o.strip() for o in extra.split(",") if o.strip())

# Validate that no empty string or null origin slips through
allow_origins = [o for o in allow_origins if o and o != "null"]
```

---

### 5.2 � LOW: No CSRF Token (Stateless CSRF)

The app relies solely on Origin/Referer header verification (double-submit cookie pattern not implemented). As shown in finding 1.3, this is bypassable.

**Suggested Fix**: Implement a token-based CSRF protection:
```python
# Generate and store a CSRF token per session
import secrets

def generate_csrf_token(session_id: str) -> str:
    return secrets.token_urlsafe(32)

# Include in HTML meta tag, require in X-CSRF-Token header for POST/PUT/DELETE
```

---

## 6. Rate Limiting

### 6.1 🟡 MEDIUM: Rate Limiting Uses Client IP (Bypassable with Proxies)

```python
# core/limiter.py
limiter = Limiter(key_func=get_remote_address)
```

`get_remote_address` uses `X-Forwarded-For` or `X-Real-IP` headers if behind a reverse proxy. If not behind a proxy, it uses the direct IP. If behind a proxy without proper configuration, attackers can forge `X-Forwarded-For` to bypass rate limits.

**Suggested Fix**:
```python
from slowapi.util import get_ipaddr  # More robust

# Or use authenticated user as rate limit key
def rate_limit_key(request: Request):
    # Prefer authenticated user ID, fall back to IP
    token = request.cookies.get("token") or request.headers.get("authorization", "")
    if token:
        return f"user:{token[:16]}"
    return f"ip:{get_ipaddr(request)}"

limiter = Limiter(key_func=rate_limit_key)
```

---

### 6.2 � LOW: No Rate Limit on Settings/Read Endpoints

Endpoints like `/api/settings` (GET), `/api/diagnostics/*`, and `/api/maintenance` have no rate limits, allowing data harvesting.

---

## 7. Session Management

### 7.1 � HIGH: Refresh Tokens Create New Sessions Without Invalidating Old Token

```python
# auth.py lines 637-658
@router.post("/refresh", ...)
async def refresh_token(current_user: ...):
    new_token = create_access_token(...)
    new_token_hash = _hash_token(new_token)
    user_sessions[new_token_hash] = {...}
    _save_sessions(user_sessions)
    # Old token still in user_sessions! Not invalidated.
```

When a user refreshes their token, the OLD token is **not** removed from the sessions dictionary. This means:
1. Token theft → attacker uses stolen token
2. User refreshes → new token issued, old still works
3. Attackers can maintain access indefinitely

**Exploitability**: EASY (once token is stolen)  
**Suggested Fix**:
```python
@router.post("/refresh", ...)
async def refresh_token(current_user: ..., 
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token_cookie: Optional[str] = Cookie(default=None, alias="token")):
    
    # Get and remove the current token
    current_token = credentials.credentials if credentials else (token_cookie or request.cookies.get("token"))
    if current_token:
        current_hash = _hash_token(current_token)
        user_sessions.pop(current_hash, None)
    
    new_token = create_access_token(...)
    new_token_hash = _hash_token(new_token)
    user_sessions[new_token_hash] = {...}
    _save_sessions(user_sessions)
```

---

### 7.2 � MEDIUM: Sessions File Stored in Web-Accessible Directory

```python
# auth.py line 235
SESSIONS_FILE = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")) / "user_sessions.json"
```

If the server is misconfigured to serve the `/app/data` directory, or if path traversal is exploited, the sessions file containing hashed JWT tokens could be downloaded.

**Suggested Fix**: 
- Ensure `.json` files in the data directory are not served
- Add Apache/Nginx rule: `location ~* \.json$ { deny all; }`
- Store sessions in `/app/sessions/` (outside static file mount)

---

### 7.3 🟢 LOW: No Session Timeout for Idle Sessions

Tokens expire after 7 days (ACCESS_TOKEN_EXPIRE_MINUTES = 10080), but there's no idle timeout. A token used once will remain valid for a full week regardless of activity.

---

## 8. Headers & Transport

### 8.1 🔴 CRITICAL: No HSTS Header

The security headers middleware (lines 360-384) does **NOT** include `Strict-Transport-Security`:

```python
# app.py — HSTS is MISSING
response.headers["X-Frame-Options"] = "DENY"
response.headers["X-Content-Type-Options"] = "nosniff"
# No Strict-Transport-Security!
```

**Exploitability**: EASY — SSL stripping attacks possible  
**Suggested Fix**:
```python
response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
```

---

### 8.2 🟡 MEDIUM: CSP Has `'unsafe-inline'` and `'unsafe-eval'` Risks

```
script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com ...
```

- `'unsafe-inline'` effectively negates much of CSP's XSS protection
- `'unsafe-eval'` is not present (good)
- However, the broad list of allowed scripts (`/static/*.js`) means any XSS in those files bypasses CSP completely

**Suggested Fix**: Remove `'unsafe-inline'` and use nonces/hashes for required inline scripts:
```python
# Generate a per-request nonce
nonce = secrets.token_urlsafe(16)
response.headers["Content-Security-Policy"] = (
    f"default-src 'self'; "
    f"script-src 'self' 'nonce-{nonce}' https://cdn.tailwindcss.com; "
    ...
)
```

---

### 8.3 � LOW: `Server` Header Exposes Uvicorn

Default Starlette/FastAPI responses include `Server: uvicorn`. While not a direct vulnerability, it aids reconnaissance.

**Suggested Fix**: Add middleware to remove/overwrite the Server header.

---

## Summary Table

| # | Finding | Severity | Exploitability---|---------|----------|----------------|----------|
| 1.1 | Multiple unprotected endpoints | � CRITICAL | EASY | AuthN/AuthZ |
| 1.2 | Unauthenticated WebSocket | 🔴 CRITICAL | EASY | AuthN |
| 1.3 | Permissive CSRF Origin check | � HIGH | MEDIUM | CSRF |
| 1.4 | Weak default admin password | 🟠 HIGH | EASY | AuthN |
| 1.5 | Plaintext secrets in config.json | 🟠 HIGH | MEDIUM | Secrets |
| 1.6 | No token revocation on password change | 🟡 MEDIUM | DIFFICULT | Session |
| 1.7 | Cookie Secure flag misconfiguration | 🟡 MEDIUM | MEDIUM | Session |
| 2.1 | No video ID validation | 🔴 CRITICAL | EASY | Validation |
| 2.2 | No max payload size | 🟠 HIGH | EASY | Validation |
| 2.3 | No username validation | 🟠 HIGH | EASY | Validation |
| 2.4 | SSRF in AI custom endpoint | 🟡 MEDIUM | MEDIUM | SSRF |
| 3.1 | SSRF in webhook test | 🟠 HIGH | EASY | SSRF |
| 3.2 | Unsanitized cookie file writes | 🟠 HIGH | MEDIUM | Injection |
| 3.3 | XSS in OAuth error response | 🟡 MEDIUM | MEDIUM | XSS |
| 3.4 | XSS payload in config.json | � LOW | N/A | Validation |
| 4.1 | Debug logging near auth tokens | 🟡 MEDIUM | N/A | Secrets |
| 4.2 | Reversible token-derived IDs | 🟡 MEDIUM | N/A | Privacy |
| 4.3 | Default password logged | 🟢 LOW | N/A | Secrets |
| 5.1 | CORS allowlist issues | � MEDIUM | MEDIUM | CORS |
| 5.2 | No CSRF token pattern | 🟢 LOW | N/A | CSRF |
| 6.1 | Rate limit key bypass | 🟡 MEDIUM | MEDIUM | Rate Limit |
| 6.2 | No rate limits on read endpoints | 🟢 LOW | N/A | Rate Limit |
| 7.1 | Refresh doesn't invalidate old token | 🟠 HIGH | EASY | Session |
| 7.2 | Sessions file in writable location | 🟡 MEDIUM | MEDIUM | Session |
| 7.3 | No idle timeout | � LOW | N/A | Session |
| 8.1 | No HSTS header | 🔴 CRITICAL | EASY | Headers |
| 8.2 | CSP allows unsafe-inline | 🟡 MEDIUM | MEDIUM | Headers |
| 8.3 | Server header disclosure | 🟢 LOW | N/A | Headers |

---

## Recommendations Priority

### Immediate (CRITICAL fixes — deploy within 24h)
1. **Add authentication to all unprotected endpoints** (1.1)
2. **Authenticate WebSocket endpoint** (1.2)
3. **Add HSTS header** (8.1)

### Short-term (HIGH fixes — within 1 week)
4. **Fix CSRF origin verification** (1.3)
5. **Enforce non-default admin password** (1.4)
6. **Validate video IDs and bulk payloads** (2.1, 2.2)
7. **Fix SSRF in webhook endpoint** (3.1)
8. **Implement token rotation with old-token invalidation** (7.1)

### Medium-term (within 1 month)
9. **Encrypt secrets at rest** (1.5)
10. **Add username/password validation** (2.3)
11. **Fix CORS and CSP policies** (5.1, 8.2)
12. **Improve rate limiting keys** (6.1)

---

## Appendix: Test Environment

During the audit, the config.json was found to contain test credentials:
```json
{
  "youtube_api_key": "test_key",
  "oauth": {"client_id": "test_id", "client_secret": "test_secret"}
}
```
This confirms the application is configured for development mode in the working directory. Ensure production deployments override these via environment variables and that the test config.json is excluded from production builds.
