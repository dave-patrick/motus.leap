"""Authentication and authorization system."""

import hashlib
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Mapping
import asyncio

from core.limiter import limiter # Import limiter from core.limiter

from fastapi import APIRouter, Depends, HTTPException, status, Cookie, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

try:
    import jwt
except ModuleNotFoundError:
    raise RuntimeError("Missing dependency: install PyJWT")

try:
    import httpx
except ModuleNotFoundError:
    raise RuntimeError("Missing dependency: install httpx")

from passlib.context import CryptContext

log = logging.getLogger(__name__)

# =============================================================================
# Persistent User Storage
# =============================================================================

# Use a directory that survives restarts on Render; project-root data/ is the
# fallback for local development. Mount a Render disk at this path for persistence.
TUBE_MANAGER_DATA_DIR = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data"))
USERS_DIR = TUBE_MANAGER_DATA_DIR
USERS_FILE = USERS_DIR / "users.json"

def _ensure_users_dir():
    USERS_DIR.mkdir(parents=True, exist_ok=True)

async def _load_users() -> Dict[str, Dict[str, Any]]:
    """Load users from JSON file."""
    if await asyncio.to_thread(USERS_FILE.exists):
        try:
            data = json.loads(await asyncio.to_thread(USERS_FILE.read_text))
            # Convert datetime strings back to datetime objects
            for u in data.values():
                for field in ("created_at", "last_login"):
                    if isinstance(u.get(field), str):
                        try:
                            u[field] = datetime.fromisoformat(u[field])
                        except (ValueError, TypeError):
                            u[field] = None
            return data
        except Exception as e:
            log.warning("Failed to load users: %s", e)
    return {}

async def _save_users(users: Dict[str, Dict[str, Any]]) -> None:
    """Save users to JSON file atomically (temp + rename to avoid partial writes), with debouncing (H13)."""
    _ensure_users_dir()
    # Convert datetime objects to ISO strings for JSON serialization
    serializable = {}
    for k, v in users.items():
        u = dict(v)
        for field in ("created_at", "last_login"):
            if isinstance(u.get(field), datetime):
                u[field] = u[field].isoformat()
        serializable[k] = u
    content = json.dumps(serializable, indent=2, default=str)
    await _debounced_write(USERS_FILE, content)


# =============================================================================
# Debounced file writes (H13)
# =============================================================================

_debounce_tasks: Dict[str, asyncio.Task] = {}
_debounce_lock = asyncio.Lock()


async def _debounced_write(path: Path, content: str, delay: float = 1.0) -> None:
    """Write to file after a debounce delay. Subsequent calls reset the timer."""
    key = str(path)
    async with _debounce_lock:
        existing = _debounce_tasks.get(key)
        if existing and not existing.done():
            existing.cancel()

    async def _do_write():
        await asyncio.sleep(delay)
        try:
            tmp = path.with_suffix(path.suffix + ".tmp")
            await asyncio.to_thread(tmp.write_text, content)
            await asyncio.to_thread(tmp.replace, path)
        except Exception as e:
            log.error("Debounced write failed for %s: %s", path, e)
        finally:
            async with _debounce_lock:
                _debounce_tasks.pop(key, None)

    task = asyncio.create_task(_do_write())
    async with _debounce_lock:
        _debounce_tasks[key] = task

# =============================================================================
# Configuration
# =============================================================================

def _load_secret_key() -> str:
    """Load a persistent HMAC secret key from environment variable.
    Falls back to an ephemeral key with a warning if not set, so the app can still boot on first deploy.
    """
    key = os.getenv("TUBE_MANAGER_SECRET_KEY", "").strip()
    if not key:
        import logging as _log
        _log.warning(
            "TUBE_MANAGER_SECRET_KEY not set - generating ephemeral secret. "
            "User sessions will NOT persist across restarts. Set the env var for stable sessions."
        )
        return os.urandom(32).hex()
    return key


SECRET_KEY = _load_secret_key()


def _cookie_secure() -> bool:
    """True when running over HTTPS in production.

    This app is deployed on Render (which sets RENDER=true), not Vercel,
    so the cookie `secure` flag must track the Render/production environment.
    Falls back to the legacy VERCEL_ENV/ENV checks for compatibility.
    Stays False for plain-http local dev so the `token` cookie is stored.
    """
    return (
        os.getenv("RENDER", "").lower() == "true"
        or os.getenv("VERCEL_ENV") == "production"
        or os.getenv("ENV") == "production"
    )


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 10080  # 7 days

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# =============================================================================
# Models
# =============================================================================

class UserCreate(BaseModel):
    """User registration request."""
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """User login request."""
    username: str
    password: str


class UserUpdate(BaseModel):
    """User update request."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    """User response."""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class PasswordResetRequest(BaseModel):
    """Password reset request."""
    username: str


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""
    username: str
    reset_token: str
    new_password: str


class RoleEnum:
    """User roles."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


# In-Memory Storage (will be loaded via dependency)
_cached_users_db: Optional[Dict[str, Dict[str, Any]]] = None

async def get_users_db() -> Dict[str, Dict[str, Any]]:
    global _cached_users_db
    if _cached_users_db is None:
        _cached_users_db = await _load_users()
    return _cached_users_db



# Allowed origins for CSRF protection. In production, this should be the domain of your frontend.
# For local development, include localhost:PORT.
# This list can be dynamically loaded from config or environment variables for more flexibility.
ALLOWED_ORIGINS = [
    "https://tubemanager.onrender.com",
    "https://motus-leap.onrender.com",
    "http://localhost:8000",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:3000",
    "http://localhost",
    "http://0.0.0.0:8000",
]

async def verify_origin(request: Request):
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")

    # Debug logging
    log.debug(f"verify_origin: origin={origin}, referer={referer}")

    # Resolve the set of app origins from config/env. Only origins that the
    # operator has explicitly declared are trusted — we no longer blanket-allow
    # every *.onrender.com subdomain (anyone can spin one up and point it at
    # the API), which was an open CSRF/credential-relay surface (M2 fix).
    allowed = set(ALLOWED_ORIGINS)
    try:
        from app import config_manager
        _cfg = config_manager.config if config_manager else None
        if _cfg is not None:
            for _o in (getattr(_cfg, "allowed_origins", None) or []):
                if _o:
                    allowed.add(_o)
    except Exception:
        pass
    # FRONTEND_URL is the canonical public origin.
    _fe = os.getenv("FRONTEND_URL", "").rstrip("/")
    if _fe:
        allowed.add(_fe)

    # If origin is present, validate it
    if origin:
        # Check exact match first
        if origin in allowed:
            return
        log.warning(f"verify_origin: BLOCKED origin={origin}")
        raise HTTPException(status_code=403, detail="Forbidden: Invalid origin")

    # If no origin header (same-origin POST forms), check referer
    if referer:
        from urllib.parse import urlparse
        ref_host = urlparse(referer).netloc
        if any(ref_host == urlparse(a).netloc for a in allowed if urlparse(a).netloc):
            return
        log.warning(f"verify_origin: BLOCKED referer={referer}")
        raise HTTPException(status_code=403, detail="Forbidden: Invalid origin")

    # No origin and no referer — likely Render health check or internal call. Allow through.
    log.debug("verify_origin: ALLOWED (no origin/referer)")
    return

SESSIONS_FILE = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")) / "user_sessions.json"


def _load_sessions() -> Dict[str, Dict[str, Any]]:
    try:
        if SESSIONS_FILE.exists():
            text = SESSIONS_FILE.read_text(encoding="utf-8")
            data = json.loads(text)
            for entry in data.values():
                for field in ("created_at", "expires_at"):
                    val = entry.get(field)
                    if isinstance(val, str):
                        try:
                            entry[field] = datetime.fromisoformat(val)
                        except (ValueError, TypeError):
                            entry[field] = None
            return data
    except Exception as e:
        log.warning("Failed to load user sessions: %s", e)
    return {}


async def _save_sessions(sessions: Dict[str, Dict[str, Any]]) -> None:
    """Save user sessions to disk with debouncing (H13)."""
    serializable: Dict[str, Dict[str, Any]] = {}
    for token, entry in sessions.items():
        s = dict(entry)
        for field in ("created_at", "expires_at"):
            val = s.get(field)
            if isinstance(val, datetime):
                s[field] = val.isoformat()
        serializable[token] = s
    content = json.dumps(serializable, indent=2, default=str)
    await _debounced_write(SESSIONS_FILE, content)


user_sessions: Dict[str, Dict[str, Any]] = _load_sessions()

# Idle session cleanup threshold (7 days)
SESSION_IDLE_CUTOFF = timedelta(days=7)


async def cleanup_idle_sessions() -> int:
    """Remove sessions older than 7 days from the in-memory sessions dict."""
    now = datetime.now()
    expired = [
        token for token, entry in user_sessions.items()
        if isinstance(entry.get("created_at"), datetime) and (now - entry["created_at"]) > SESSION_IDLE_CUTOFF
    ]
    for token in expired:
        user_sessions.pop(token, None)
    if expired:
        log.info(f"Session cleanup: removed {expired.__len__()} idle sessions")
    return len(expired)

# Token revocation list — stores hashes of revoked tokens
_revoked_tokens: set = set()


def _hash_token(token: str) -> str:
    """Hash a token for secure storage on disk."""
    return hashlib.sha256(token.encode()).hexdigest()


def is_token_revoked(token: str) -> bool:
    """Check if a token has been revoked."""
    return _hash_token(token) in _revoked_tokens


def revoke_token(token: str) -> None:
    """Add a token's hash to the revocation list."""
    _revoked_tokens.add(_hash_token(token))


# =============================================================================
# Helpers
# =============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_user_by_username(username: str, users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db)) -> Optional[Dict[str, Any]]:
    return users_db.get(username)


async def get_user_by_id(user_id: str, users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db)) -> Optional[Dict[str, Any]]:
    for user in users_db.values():
        if user["id"] == user_id:
            return user
    return None


async def authenticate_user(username: str, password: str, users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db)) -> Optional[Dict[str, Any]]:
    user = await get_user_by_username(username, users_db) # Await the async function
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    user["last_login"] = datetime.now()
    await _save_users(users_db) # Save changes to users_db
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    request: Request = None,
    token_cookie: Optional[str] = Cookie(default=None, alias="token"),
    users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db),
) -> Dict[str, Any]:
    token = None
    if credentials:
        token = credentials.credentials
    elif token_cookie:
        token = token_cookie
    elif request:
        token = request.cookies.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)

    # Check if token has been revoked
    if is_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username: str = payload.get("sub")

    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_username(username, users_db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not current_user.get("is_active", True):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def check_role(required_roles: List[str]):
    async def role_checker(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        if current_user["role"] not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user
    return role_checker


def get_user_permissions(role: str) -> List[str]:
    role_permissions = {
        "admin": [
            "users:read", "users:write", "users:delete",
            "playlists:read", "playlists:write", "playlists:delete",
            "subscriptions:read", "subscriptions:write", "subscriptions:delete",
            "mappings:read", "mappings:write", "mappings:delete",
            "config:read", "config:write",
            "bulk:read", "bulk:write",
        ],
        "user": [
            "playlists:read", "playlists:write",
            "subscriptions:read",
            "mappings:read", "mappings:write",
            "config:read",
            "bulk:read", "bulk:write",
        ],
        "viewer": [
            "playlists:read",
            "subscriptions:read",
            "mappings:read",
            "config:read",
            "bulk:read",
        ],
    }

    return role_permissions.get(role, [])


# =============================================================================
# Auth Endpoints
# =============================================================================

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_origin)])
@limiter.limit("5/minute")
async def register(user_data: UserCreate, request: Request, users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db)):
    # Gate open self-registration behind a disabled-by-default config flag.
    # The app must not expose a public sign-up surface unless the operator
    # explicitly enables it (M1 security fix).
    from app import config_manager
    _cfg = config_manager.config if config_manager else None
    if not (_cfg and getattr(_cfg, "allow_self_registration", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-registration is disabled",
        )

    username_check = (user_data.username or "").strip()
    password_check = (user_data.password or "").strip()
    if not username_check or not password_check:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request payload")

    if await get_user_by_username(user_data.username, users_db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    for user_entry in users_db.values():
        if user_entry["email"] == user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    user_id = secrets.token_hex(16)

    user = {
        "id": user_id,
        "username": user_data.username,
        "email": user_data.email,
        "full_name": user_data.full_name,
        "hashed_password": get_password_hash(user_data.password),
        "role": "user",
        "is_active": True,
        "created_at": datetime.now(),
        "last_login": datetime.now(),
    }

    users_db[user_data.username] = user
    await _save_users(users_db)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=access_token_expires,
    )

    token_hash = _hash_token(access_token)
    user_sessions[token_hash] = {
        "user_id": user["id"],
        "username": user["username"],
        "created_at": datetime.now(),
        "expires_at": datetime.now() + access_token_expires,
    }
    await _save_sessions(user_sessions)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(**user),
    )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(verify_origin)])
@limiter.limit("5/minute")
async def login(user_data: UserLogin, request: Request, response: Response, users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db)):
    user = await authenticate_user(user_data.username, user_data.password, users_db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=access_token_expires,
    )

    token_hash = _hash_token(access_token)
    user_sessions[token_hash] = {
        "user_id": user["id"],
        "username": user["username"],
        "created_at": datetime.now(),
        "expires_at": datetime.now() + access_token_expires,
    }
    await _save_sessions(user_sessions)

    # Replace token cookie using matching attributes.
    response.delete_cookie(
        key="token",
        path="/",
        httponly=True,
        samesite="Lax",
        secure=_cookie_secure(),
    )
    response.set_cookie(
        key="token",
        value=access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        httponly=True,
        samesite="Lax",
        secure=_cookie_secure(),
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(**user),
    )


def _now() -> datetime:
    return datetime.now()


def _clean_expired_tokens(entry: Dict[str, Any]) -> None:
    reset_tokens = entry.get("reset_tokens") or {}
    expired = [k for k, v in reset_tokens.items() if _now() > datetime.fromisoformat(v["expires_at"])]
    for k in expired:
        reset_tokens.pop(k, None)


@router.post("/password-reset", response_model=dict, dependencies=[Depends(verify_origin)])
@limiter.limit("10/minute")
async def request_password_reset(request: Request, body: PasswordResetRequest, users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db)):
    """Request a password reset token. Always returns success, even if user is not found."""
    user = await get_user_by_username(body.username, users_db)
    if user:
        reset_token = secrets.token_urlsafe(32)
        expires_at = (_now() + timedelta(minutes=15)).isoformat()
        user.setdefault("reset_tokens", {})[reset_token] = {
            "created_at": _now().isoformat(),
            "expires_at": expires_at,
        }
        await _save_users(users_db)
        return {"message": "If that account exists, a reset has been prepared."}
    return {"message": "If that account exists, a reset has been prepared."}


@router.post("/password-reset/confirm", response_model=dict, dependencies=[Depends(verify_origin)])
@limiter.limit("10/minute")
async def confirm_password_reset(request: Request, body: PasswordResetConfirm, users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db)):
    """Confirm password reset with username and token. Returns success or error."""
    user = await get_user_by_username(body.username, users_db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    reset_tokens = user.get("reset_tokens") or {}
    token_meta = reset_tokens.get(body.reset_token)
    if not token_meta:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")
    try:
        expires_at = datetime.fromisoformat(token_meta["expires_at"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")
    if _now() > expires_at:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Reset token expired")
    user["hashed_password"] = get_password_hash(body.new_password)
    user.pop("reset_tokens", None)
    await _save_users(users_db)
    return {"message": "Password has been reset"}


@router.post("/logout", dependencies=[Depends(verify_origin)])
async def logout(
    request: Request,
    response: Response, # Add response to clear cookie
    current_user: Dict[str, Any] = Depends(get_current_user),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token_cookie: Optional[str] = Cookie(default=None, alias="token"),
):
    token = None
    if credentials:
        token = credentials.credentials
    elif token_cookie:
        token = token_cookie
    elif request:
        token = request.cookies.get("token")

    if token:
        token_hash = _hash_token(token)
        user_sessions.pop(token_hash, None)
        await _save_sessions(user_sessions)
    
    # Clear the cookie on logout
    response.delete_cookie(
        key="token",
        path="/",
        httponly=True,
        samesite="Lax",
        secure=_cookie_secure(),
    )

    log.info("User '%s' logged out, token invalidated", current_user["username"])
    return {"message": "Successfully logged out"}


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(verify_origin)])
async def refresh_token(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token_cookie: Optional[str] = Cookie(default=None, alias="token"),
):
    """Issue a fresh 7-day token and invalidate the old one (rotation)."""
    # Extract old token for revocation
    old_token = None
    if credentials:
        old_token = credentials.credentials
    elif token_cookie:
        old_token = token_cookie
    elif request:
        old_token = request.cookies.get("token")

    # Revoke the old token if present
    if old_token:
        revoke_token(old_token)
        old_hash = _hash_token(old_token)
        user_sessions.pop(old_hash, None)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_token = create_access_token(
        data={"sub": current_user["username"], "role": current_user["role"]},
        expires_delta=access_token_expires,
    )
    new_token_hash = _hash_token(new_token)
    user_sessions[new_token_hash] = {
        "user_id": current_user["id"],
        "username": current_user["username"],
        "created_at": datetime.now(),
        "expires_at": datetime.now() + access_token_expires,
    }
    await _save_sessions(user_sessions)
    return TokenResponse(
        access_token=new_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(**current_user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    return UserResponse(**current_user)


@router.get("/security/status", response_model=Dict[str, Any], dependencies=[Depends(check_role([RoleEnum.ADMIN]))])
async def security_status():
    """Expose whether the JWT secret is configured for stable sessions."""
    secret_from_env = bool(os.getenv("TUBE_MANAGER_SECRET_KEY", "").strip())
    return {
        "secret_key_from_env": secret_from_env,
        "sessions_stable": secret_from_env,
        "warning": None if secret_from_env else (
            "TUBE_MANAGER_SECRET_KEY is not set. Sessions will be invalidated on every "
            "Render restart or deploy. Add TUBE_MANAGER_SECRET_KEY to your Render "
            "Dashboard Environment Variables to keep sessions stable."
        ),
    }


@router.put("/me", response_model=UserResponse, dependencies=[Depends(verify_origin)])
async def update_me(
    user_update: UserUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db),
):
    if user_update.email:
        for user_entry in users_db.values():
            if user_entry["email"] == user_update.email and user_entry["id"] != current_user["id"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use",
                )
        current_user["email"] = user_update.email

    if user_update.full_name:
        current_user["full_name"] = user_update.full_name
    
    users_db[current_user["username"]] = current_user
    await _save_users(users_db)

    return UserResponse(**current_user)

# =============================================================================
# User Management Endpoints (Admin only)
# =============================================================================

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: Dict[str, Any] = Depends(check_role(["admin"])),
    users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db), # Add users_db dependency
):
    return [UserResponse(**user) for user in users_db.values()]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(check_role(["admin"])),
    users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db), # Add users_db dependency
):
    user = await get_user_by_id(user_id, users_db) # Await call
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(**user)


@router.put("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(verify_origin)])
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: Dict[str, Any] = Depends(check_role(["admin"])),
    users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db), # Add users_db dependency
):
    user = await get_user_by_id(user_id, users_db) # Await call
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user_update.email:
        user["email"] = user_update.email

    if user_update.full_name:
        user["full_name"] = user_update.full_name

    if user_update.role:
        user["role"] = user_update.role

    users_db[user["username"]] = user # Update the entry in the in-memory db
    await _save_users(users_db) # Persist the changes
    return UserResponse(**user)


@router.delete("/users/{user_id}", dependencies=[Depends(verify_origin)])
async def delete_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(check_role(["admin"])),
    users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db), # Add users_db dependency
):
    user = await get_user_by_id(user_id, users_db) # Await call
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user["id"] == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )

    username_to_delete = user["username"]
    del users_db[username_to_delete]
    await _save_users(users_db) # Persist the changes
    return {"message": f"User {username_to_delete} deleted"}


# =============================================================================
# Initialization
# =============================================================================

async def create_default_admin() -> None:
    users_db = await get_users_db() # Get the users_db
    if not users_db:
        default_password = os.getenv("TUBE_MANAGER_ADMIN_PASSWORD", "admin")
        if default_password == "admin":
            log.warning(
                "Using default admin password 'admin'. "
                "Set TUBE_MANAGER_ADMIN_PASSWORD env var to change."
            )

        user_id = secrets.token_hex(16)
        users_db["admin"] = {
            "id": user_id,
            "username": "admin",
            "email": "admin@example.com",
            "full_name": "Default Admin",
            "hashed_password": get_password_hash(default_password),
            "role": "admin",
            "is_active": True,
            "created_at": datetime.now(),
            "last_login": None,
        }
        await _save_users(users_db) # Save changes
        log.info("Default admin user created (username: admin)")


# =============================================================================
# Google OAuth Login
# =============================================================================

import os
from pathlib import Path

def resolve_oauth_credentials(env: "Mapping[str, str]", config_dir: Optional[Path] = None) -> tuple[str, str]:
    """Resolve (client_id, client_secret) from env vars then config.json.

    Env precedence (canonical name wins over the alias Render injects):
      GOOGLE_OAUTH_CLIENT_ID    > YOUTUBE_CLIENT_ID
      GOOGLE_OAUTH_CLIENT_SECRET > YOUTUBE_CLIENT_SECRET
    Falls back to config.json's ``oauth`` block (the in-app Settings save
    writes there). ``env`` is injected so the resolver is pure/testable; the
    module-level loader passes ``os.environ``.
    """
    def _env_get(*names: str) -> str:
        for n in names:
            v = (env.get(n) or "").strip()
            if v:
                return v
        return ""

    client_id = _env_get("GOOGLE_OAUTH_CLIENT_ID", "YOUTUBE_CLIENT_ID")
    client_secret = _env_get("GOOGLE_OAUTH_CLIENT_SECRET", "YOUTUBE_CLIENT_SECRET")

    # Fallback: load from config.json (the in-app Settings save path writes here)
    if not client_id or not client_secret:
        try:
            base = config_dir or Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data"))
            config_file = base / "config.json"
            if config_file.exists():
                with open(config_file) as f:
                    config = json.load(f)
                oauth = config.get("oauth", {})
                if not client_id:
                    client_id = (oauth.get("client_id") or "").strip()
                if not client_secret:
                    client_secret = (oauth.get("client_secret") or "").strip()
        except Exception:
            pass

    return client_id, client_secret


def _load_oauth_credentials():
    """Module entrypoint: resolve OAuth creds from the live process env."""
    return resolve_oauth_credentials(os.environ)

GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET = _load_oauth_credentials()
GOOGLE_OAUTH_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "https://tubemanager.onrender.com/api/auth/google/callback")


def _resolve_oauth_credentials() -> tuple[str, str]:
    """Resolve live OAuth credentials for a request.

    The module-level GOOGLE_OAUTH_CLIENT_ID/SECRET constants are captured at
    import and DO NOT reflect credentials saved via the Settings UI after
    startup. This helper resolves them fresh on every call:

      1. environment variables (GOOGLE_OAUTH_* then YOUTUBE_* alias)
      2. the live in-app config (config_manager.config.oauth — updated by the
         Settings save handler without a restart)
      3. config.json on disk (resolve_oauth_credentials)

    Returns (client_id, client_secret), both stripped; either may be empty.
    """
    client_id, client_secret = resolve_oauth_credentials(os.environ)
    if client_id and client_secret:
        return client_id, client_secret

    # Fall back to the live in-app config (reflects Settings UI saves).
    try:
        from app import config_manager as app_cm

        def _as_str(val: object) -> str:
            if val is None:
                return ""
            if hasattr(val, "get_secret_value"):
                return str(val.get_secret_value())  # type: ignore[attr-defined]
            return str(val)

        if app_cm and getattr(app_cm.config, "oauth", None):
            cid = _as_str(app_cm.config.oauth.client_id).strip()
            sec = _as_str(app_cm.config.oauth.client_secret).strip()
            if cid and sec:
                return cid, sec
    except Exception:
        pass

    return "", ""


@router.get("/google")
async def google_oauth_init(request: Request):
    """Initiate Google OAuth flow for user login.

    When called by a browser (no Accept: application/json and no ?format=json),
    returns a 302 redirect to Google's auth URL.  API clients that request JSON
    get the auth_url in a JSON body instead.
    """
    client_id, _ = _resolve_oauth_credentials()
    if not client_id:
        return {"error": "Google OAuth not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET env vars or configure in Settings."}

    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={GOOGLE_OAUTH_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile"
        f"&access_type=offline"
        f"&prompt=consent%20select_account"
    )

    # API clients explicitly request JSON via header or query param
    accept_header = request.headers.get("accept", "")
    format_param = request.query_params.get("format", "")
    wants_json = "application/json" in accept_header or format_param == "json"

    if wants_json:
        return {"auth_url": auth_url}

    # Browser navigation: redirect directly to Google
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get("/youtube")
async def youtube_oauth_init():
    """Initiate YouTube OAuth flow for data access (separate from login).
    
    Checks environment variables first, falls back to config.json settings.
    """
    client_id, client_secret = _resolve_oauth_credentials()
    if not client_id:
        return {"error": "Google OAuth not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET env vars or configure in Settings."}

    # Use the same callback as login, but with a state parameter to identify it as YouTube OAuth
    state = secrets.token_urlsafe(16)
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={GOOGLE_OAUTH_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube"
        f"&access_type=offline"
        f"&prompt=consent%20select_account"
        f"&state={state}&include_granted_scopes=true"
    )
    # Store state to identify this as YouTube OAuth on callback
    _youtube_oauth_states[state] = True
    return {"auth_url": auth_url}

# Track YouTube OAuth states
_youtube_oauth_states: dict[str, bool] = {}


# Note: YouTube OAuth callback is handled by /google/callback above,
# which checks the state parameter to identify YouTube OAuth flows.


@router.get("/google/callback")
async def google_oauth_callback(code: str, state: str = None, response: Response = None): # Added response here
    """Handle Google OAuth callback. If state is a YouTube OAuth state, save YouTube tokens."""
    cb_client_id, cb_client_secret = _resolve_oauth_credentials()
    if not cb_client_id or not cb_client_secret:
        return HTMLResponse("""
            <h1 style="color: #ff4444;">❌ Google OAuth Not Configured</h1>
            <p>Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET environment variables, or configure OAuth in Settings.</p>
        """, status_code=400)

    # Check if this is a YouTube OAuth callback
    is_youtube_oauth = state and _youtube_oauth_states.pop(state, False)

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": cb_client_id,
        "client_secret": cb_client_secret,
        "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(token_url, data=data)
            tokens = resp.json()

        if "access_token" not in tokens:
            error_msg = tokens.get("error_description", tokens.get("error", str(tokens)))
            return HTMLResponse(f"""
                <h1 style="color: #ff4444;">❌ OAuth Error</h1>
                <p><strong>Error:</strong> {error_msg}</p>
            """, status_code=400)

        # If YouTube OAuth, save tokens and show success
        if is_youtube_oauth:
            # Use the app's running config manager/service so the in-memory
            # YouTubeService picks up the new tokens immediately.
            try:
                from app import config_manager as app_config_manager, youtube_service as app_youtube_service
                cm = app_config_manager
            except Exception:
                from core.config_manager import ConfigManager
                from pathlib import Path
                cm = ConfigManager(Path("/app/data/config.json") if Path("/app/data").exists() else Path("config.json"))
                app_youtube_service = None

            config = cm.config
            config.oauth.access_token = tokens["access_token"]
            config.oauth.refresh_token = tokens.get("refresh_token", "")
            config.oauth.token_expiry = int(time.time()) + tokens.get("expires_in", 3600)
            await cm.save(config) # Await the save

            # Force the running YouTubeService to rebuild its client with new tokens
            if app_youtube_service is not None:
                app_youtube_service._client = None

            frontend_url = os.getenv("FRONTEND_URL", "https://tubemanager.onrender.com").rstrip("/")
            return RedirectResponse(url=f"{frontend_url}/auth?status=success&type=youtube", status_code=302)

        # Otherwise, handle as user login (existing flow below)
        access_token = tokens["access_token"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            userinfo = userinfo_resp.json()

        google_id = userinfo.get("id")
        email = userinfo.get("email")
        name = userinfo.get("name", "")
        picture = userinfo.get("picture", "")

        if not email:
            return HTMLResponse("""
                <h1 style="color: #ff4444;">❌ OAuth Error</h1>
                <p>Could not retrieve email from Google account.</p>
            """, status_code=400)

        # Check if user exists by email
        existing_user = None
        users_db_loaded = await get_users_db() # Load users_db
        for user in users_db_loaded.values():
            if user["email"] == email:
                existing_user = user
                break

        if existing_user:
            user = existing_user
            # Update profile info from Google
            user["full_name"] = name
            if picture:
                user["avatar_url"] = picture
        else:
            # Create new user
            username = email.split("@")[0]
            # Ensure unique username
            base_username = username
            counter = 1
            while await get_user_by_username(username, users_db_loaded): # Await get_user_by_username
                username = f"{base_username}{counter}"
                counter += 1

            user_id = secrets.token_hex(16)
            user = {
                "id": user_id,
                "username": username,
                "email": email,
                "full_name": name,
                "avatar_url": picture,
                "hashed_password": "",  # No password for OAuth users
                "role": "user",
                "is_active": True,
                "created_at": datetime.now(),
                "last_login": datetime.now(),
            }
            users_db_loaded[username] = user
            await _save_users(users_db_loaded)

        user["last_login"] = datetime.now()
        await _save_users(users_db_loaded) # Save updated user data

        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        app_token = create_access_token(
            data={"sub": user["username"], "role": user["role"]},
            expires_delta=access_token_expires,
        )

        app_token_hash = _hash_token(app_token)
        user_sessions[app_token_hash] = {
            "user_id": user["id"],
            "username": user["username"],
            "created_at": datetime.now(),
            "expires_at": datetime.now() + access_token_expires,
        }

        # Set the token in a secure, http-only cookie for OAuth login
        # IMPORTANT: the cookie MUST be set on the RedirectResponse that is
        # returned. Setting it on a separate injected Response object is
        # discarded by Starlette — the browser then never stores the token,
        # require_auth redirects to /auth, and the user loops.
        frontend_url = os.getenv("FRONTEND_URL", "https://tubemanager.onrender.com").rstrip("/")
        redirect = RedirectResponse(
            url=f"{frontend_url}/dashboard#token={app_token}",
            status_code=302
        )
        redirect.set_cookie(
            key="token",
            value=app_token,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
            httponly=True,
            samesite="Lax",
            secure=_cookie_secure(),
        )
        return redirect

    except httpx.RequestError as e:
        log.error(f"HTTP request failed: {e}")
        return HTMLResponse(f"""
            <h1 style="color: #ff4444;">❌ Network Error</h1>
            <p>Failed to connect to Google: {str(e)}</p>
        """, status_code=500)
    except Exception as e:
        log.exception("Unexpected error in Google OAuth callback")
        return HTMLResponse(f"""
            <h1 style="color: #ff4444;">❌ Server Error</h1>
            <p>{str(e)}</p>
        """, status_code=500)


# Call this at startup to ensure a default admin user exists
# But make sure it's awaited if called from an async context or run in a thread

