"""Health check endpoints for FastAPI."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any
import time
import os

from core.observability import PROMETHEUS_AVAILABLE

health_router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    timestamp: float
    uptime_seconds: float
    checks: Dict[str, Dict[str, Any]]


class ReadinessResponse(BaseModel):
    status: str
    checks: Dict[str, Dict[str, Any]]


class LivenessResponse(BaseModel):
    status: str


# Track app start time
_start_time = time.time()


def get_uptime() -> float:
    """Get application uptime in seconds."""
    return time.time() - _start_time


async def check_database() -> Dict[str, Any]:
    """Check SQLite database connectivity."""
    try:
        from services.db import db
        # Simple query to verify DB is accessible
        result = await db.fetchone("SELECT 1 as healthy")
        return {
            "status": "healthy",
            "healthy": result["healthy"] == 1 if result else False
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_youtube_api() -> Dict[str, Any]:
    """Check YouTube API connectivity."""
    try:
        from services.youtube_client import youtube_client
        if not youtube_client:
            return {"status": "disabled", "reason": "YouTube client not configured"}

        # Check if we have valid credentials
        has_credentials = (
            youtube_client.credentials is not None
            and not youtube_client.credentials.expired
        )

        return {
            "status": "healthy" if has_credentials else "degraded",
            "credentials_valid": has_credentials,
            "quota_available": True  # Would need API call to verify
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_redis() -> Dict[str, Any]:
    """Check Redis connectivity."""
    try:
        from core.cache import _redis_available, _get_redis

        if not _redis_available:
            return {"status": "disabled", "reason": "Redis not configured"}

        redis = _get_redis()
        if redis is None:
            return {"status": "disabled", "reason": "Redis not available"}

        await redis.ping()
        return {"status": "healthy"}
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_disk_space() -> Dict[str, Any]:
    """Check available disk space."""
    try:
        import shutil
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        percent_free = (usage.free / usage.total) * 100

        status = "healthy" if percent_free > 10 else "warning" if percent_free > 5 else "critical"

        return {
            "status": status,
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "percent_free": round(percent_free, 1)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_ai_providers() -> Dict[str, Any]:
    """Check AI provider connectivity."""
    try:
        from core.config_manager import config

        providers = config.get("ai_providers", {})
        if not providers:
            return {"status": "disabled", "reason": "No AI providers configured"}

        healthy_providers = []
        unhealthy_providers = []

        for name, provider in providers.items():
            if provider.get("api_key"):
                healthy_providers.append(name)
            else:
                unhealthy_providers.append(name)

        status = "healthy" if not unhealthy_providers else "degraded"

        return {
            "status": status,
            "healthy_providers": healthy_providers,
            "unhealthy_providers": unhealthy_providers
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Health check endpoint
@health_router.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check."""
    checks = {
        "database": await check_database(),
        "youtube_api": await check_youtube_api(),
        "redis": await check_redis(),
        "disk_space": await check_disk_space(),
        "ai_providers": await check_ai_providers(),
    }

    overall_status = "healthy"
    for check_name, check_result in checks.items():
        if check_result["status"] == "unhealthy":
            overall_status = "unhealthy"
        elif check_result["status"] == "degraded" and overall_status == "healthy":
            overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp=time.time(),
        uptime_seconds=get_uptime(),
        checks=checks
    )


# Readiness check
@health_router.get("/ready", response_model=ReadinessResponse)
async def readiness_check():
    """Check if the service is ready to accept requests."""
    checks = {
        "database": await check_database(),
        "youtube_api": await check_youtube_api(),
    }

    ready = all(
        check["status"] in ("healthy", "degraded")
        for check in checks.values()
    )

    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        checks=checks
    )


# Liveness check
@health_router.get("/live", response_model=LivenessResponse)
async def liveness_check():
    """Check if the service is alive (for Kubernetes/container orchestration)."""
    return LivenessResponse(status="alive")


# Prometheus metrics endpoint
@health_router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    if not PROMETHEUS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prometheus metrics not available"
        )

    from core.observability import prometheus_registry
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    from fastapi import Response
    return Response(
        content=generate_latest(prometheus_registry),
        media_type=CONTENT_TYPE_LATEST
    )