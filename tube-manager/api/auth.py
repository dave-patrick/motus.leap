"""Authentication and authorization system."""

import logging

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import os
import secrets
import jwt
from passlib.context import CryptContext

log = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

SECRET_KEY = os.getenv("TUBE_MANAGER_SECRET_KEY") or secrets.token_urlsafe(32)
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
# In-Memory Storage (Use database in production)
# =============================================================================

users_db: Dict[str, Dict[str, Any]] = {}
user_sessions: Dict[str, Dict[str, Any]] = {}


# =============================================================================
# Helper Functions
# =============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT token."""
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
    """Get a user by username."""
    return users_db.get(username)


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get a user by ID."""
    for user in users_db.values():
        if user["id"] == user_id:
            return user
    return None


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user."""
    user = get_user_by_username(username)

    if not user:
        return None

    if not verify_password(password, user["hashed_password"]):
        return None

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    # Update last login
    user["last_login"] = datetime.now()

    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Get the current authenticated user."""
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
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get the current active user."""
    if not current_user.get("is_active", True):
        raise HTTPException(status_code=400, detail="Inactive user")

    return current_user


def check_role(required_roles: List[str]):
    """Check if user has required role."""
    async def role_checker(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        if current_user["role"] not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user

    return role_checker


def check_permission(permission: str):
    """Check if user has specific permission."""
    async def permission_checker(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        user_permissions = get_user_permissions(current_user["role"])

        if permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )

        return current_user

    return permission_checker


def get_user_permissions(role: str) -> List[str]:
    """Get permissions for a role."""
    role_permissions = {
        "admin": [
            "users:read", "users:write", "users:delete",
            "playlists:read", "playlists:write", "playlists:delete",
            "subscriptions:read", "subscriptions:write", "subscriptions:delete",
            "mappings:read", "mappings:write", "mappings:delete",
            "config:read", "config:write",
            "bulk:read", "bulk:write"
        ],
        "user": [
            "playlists:read", "playlists:write",
            "subscriptions:read",
            "mappings:read", "mappings:write",
            "config:read",
            "bulk:read", "bulk:write"
        ],
        "viewer": [
            "playlists:read",
            "subscriptions:read",
            "mappings:read",
            "config:read",
            "bulk:read"
        ]
    }

    return role_permissions.get(role, [])


# =============================================================================
# Auth Endpoints
# =============================================================================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """Register a new user."""
    if get_user_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Check if email is already used
    for user in users_db.values():
        if user["email"] == user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    user_id = secrets.token_hex(16)

    user = {
        "id": user_id,
        "username": user_data.username,
        "email": user_data.email,
        "full_name": user_data.full_name,
        "hashed_password": get_password_hash(user_data.password),
        "role": "user",  # Default role
        "is_active": True,
        "created_at": datetime.now(),
        "last_login": None
    }

    users_db[user_data.username] = user

    return UserResponse(**user)


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    """Login a user and return access token."""
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
        expires_delta=access_token_expires
    )

    # Store session
    user_sessions[access_token] = {
        "user_id": user["id"],
        "username": user["username"],
        "created_at": datetime.now(),
        "expires_at": datetime.now() + access_token_expires
    }

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(**user)
    )


@router.post("/logout")
async def logout(
    current_user: Dict[str, Any] = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Logout the current user and invalidate the token."""
    token = credentials.credentials
    user_sessions.pop(token, None)
    log.info(f"User '{current_user['username']}' logged out, token invalidated")
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get current user information."""
    return UserResponse(**current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    user_update: UserUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Update current user information."""
    if user_update.email:
        # Check if email is already used by another user
        for user in users_db.values():
            if user["email"] == user_update.email and user["id"] != current_user["id"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use"
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
    current_user: Dict[str, Any] = Depends(check_role(["admin"]))
):
    """List all users (admin only)."""
    return [UserResponse(**user) for user in users_db.values()]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(check_role(["admin"]))
):
    """Get a specific user (admin only)."""
    user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse(**user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: Dict[str, Any] = Depends(check_role(["admin"]))
):
    """Update a user (admin only)."""
    user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
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
    current_user: Dict[str, Any] = Depends(check_role(["admin"]))
):
    """Delete a user (admin only)."""
    user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user["id"] == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )

    # Delete user
    username_to_delete = user["username"]
    del users_db[username_to_delete]

    return {"message": f"User {username_to_delete} deleted"}


# =============================================================================
# Initialization
# =============================================================================

def create_default_admin() -> None:
    """Create default admin user if no users exist."""
    if not users_db:
        import os
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
        log.info(f"Default admin user created (username: admin)")


create_default_admin()
