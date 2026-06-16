"""Authentication and authorization system."""

import logging
import os
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
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
# Configuration
# =============================================================================

SECRET_KEY = os.getenv("TUBE_MANAGER_SECRET_KEY")
if not SECRET_KEY:
    secret_path = Path(__file__).resolve().parent / ".secret"
    try:
        if secret_path.exists():
            SECRET_KEY = secret_path.read_text(encoding="utf-8").strip()
        else:
            SECRET_KEY = secrets.token_urlsafe(32)
            secret_path.write_text(SECRET_KEY, encoding="utf-8")
    except Exception as exc:
        raise RuntimeError(
            "Missing TUBE_MANAGER_SECRET_KEY and unable to persist a fallback secret"
        ) from exc

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer()

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
    role: Optional[str] = None


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


class RoleEnum:
    """User roles."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


# =============================================================================
# In-Memory Storage
# =============================================================================

users_db: Dict[str, Dict[str, Any]] = {}
user_sessions: Dict[str, Dict[str, Any]] = {}


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
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

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
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    return users_db.get(username)


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    for user in users_db.values():
        if user["id"] == user_id:
            return user
    return None


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    user = get_user_by_username(username)
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
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    token = credentials.credentials
    payload = decode_access_token(token)
    username: str = payload.get("sub")

    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_username(username)
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

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    if get_user_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    for user in users_db.values():
        if user["email"] == user_data.email:
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
        "last_login": None,
    }

    users_db[user_data.username] = user
    return UserResponse(**user)


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    user = authenticate_user(user_data.username, user_data.password)
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

    user_sessions[access_token] = {
        "user_id": user["id"],
        "username": user["username"],
        "created_at": datetime.now(),
        "expires_at": datetime.now() + access_token_expires,
    }

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(**user),
    )


@router.post("/logout")
async def logout(
    current_user: Dict[str, Any] = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials
    user_sessions.pop(token, None)
    log.info("User '%s' logged out, token invalidated", current_user["username"])
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    return UserResponse(**current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    user_update: UserUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    if user_update.email:
        for user in users_db.values():
            if user["email"] == user_update.email and user["id"] != current_user["id"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use",
                )
        current_user["email"] = user_update.email

    if user_update.full_name:
        current_user["full_name"] = user_update.full_name

    return UserResponse(**current_user)


# =============================================================================
# User Management Endpoints (Admin only)
# =============================================================================

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: Dict[str, Any] = Depends(check_role(["admin"])),
):
    return [UserResponse(**user) for user in users_db.values()]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(check_role(["admin"])),
):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(**user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: Dict[str, Any] = Depends(check_role(["admin"])),
):
    user = get_user_by_id(user_id)
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

    return UserResponse(**user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(check_role(["admin"])),
):
    user = get_user_by_id(user_id)
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
    return {"message": f"User {username_to_delete} deleted"}


# =============================================================================
# Initialization
# =============================================================================

def create_default_admin() -> None:
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
        log.info("Default admin user created (username: admin)")


# =============================================================================
# Google OAuth Login
# =============================================================================

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "https://tubemanager.onrender.com/api/auth/google/callback")


@router.get("/google")
async def google_oauth_init():
    """Initiate Google OAuth flow for user login."""
    if not GOOGLE_OAUTH_CLIENT_ID:
        return {"error": "Google OAuth not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET env vars."}

    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_OAUTH_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_OAUTH_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return {"auth_url": auth_url}


@router.get("/youtube")
async def youtube_oauth_init():
    """Initiate YouTube OAuth flow for data access (separate from login)."""
    if not GOOGLE_OAUTH_CLIENT_ID:
        return {"error": "Google OAuth not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET env vars."}

    # Use the same callback as login, but with a state parameter to identify it as YouTube OAuth
    state = secrets.token_urlsafe(16)
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_OAUTH_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_OAUTH_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube"
        f"&access_type=offline"
        f"&prompt=consent"
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
async def google_oauth_callback(code: str, state: str = None):
    """Handle Google OAuth callback. If state is a YouTube OAuth state, save YouTube tokens."""
    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
        return HTMLResponse("""
            <h1 style="color: #ff4444;">❌ Google OAuth Not Configured</h1>
            <p>Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET environment variables.</p>
        """, status_code=400)

    # Check if this is a YouTube OAuth callback
    is_youtube_oauth = state and _youtube_oauth_states.pop(state, False)

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
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
            from core.config_manager import ConfigManager
            from pathlib import Path
            cm = ConfigManager(Path("/app/data/config.json") if Path("/app/data").exists() else Path("config.json"))
            config = cm.config
            config.oauth.access_token = tokens["access_token"]
            config.oauth.refresh_token = tokens.get("refresh_token", "")
            config.oauth.token_expiry = int(time.time()) + tokens.get("expires_in", 3600)
            cm.save(config)
            return HTMLResponse("""
                <div style="background: #0a0c10; color: #e5e5e5; font-family: Inter, sans-serif; padding: 40px; text-align: center; min-height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                    <h1 style="color: #44ff88;">✅ YouTube Connected!</h1>
                    <p style="color: #9ca3af; margin: 16px 0;">Your YouTube account has been connected successfully.</p>
                    <p style="color: #6b7280; font-size: 12px;">You can close this window and return to <a href="/settings" style="color: #60a5fa;">Settings</a></p>
                    <script>try { window.opener && window.opener.postMessage({type: 'youtube-oauth-success'}, '*'); } catch(e) {}</script>
                </div>
            """)

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
        for user in users_db.values():
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
            while get_user_by_username(username):
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
            users_db[username] = user

        user["last_login"] = datetime.now()

        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        app_token = create_access_token(
            data={"sub": user["username"], "role": user["role"]},
            expires_delta=access_token_expires,
        )

        user_sessions[app_token] = {
            "user_id": user["id"],
            "username": user["username"],
            "created_at": datetime.now(),
            "expires_at": datetime.now() + access_token_expires,
        }

        # Redirect to dashboard with token in URL fragment (for SPA)
        frontend_url = os.getenv("FRONTEND_URL", "https://tubemanager.onrender.com").rstrip("/")
        return RedirectResponse(
            url=f"{frontend_url}/dashboard#token={app_token}",
            status_code=302
        )

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


create_default_admin()
