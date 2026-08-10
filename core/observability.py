"""Observability: health checks, metrics, and error tracking for motus.leap."""

import os
import time
import logging
from typing import Any, Dict

from fastapi import Request
from fastapi.responses import JSONResponse

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_PROMETHEUS
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

log = logging.getLogger(__name__)

# Prometheus metrics
if PROMETHEUS_AVAILABLE:
    REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
    REQUEST_DURATION = Histogram("http_request_duration_seconds", "HTTP request duration", ["method", "endpoint"])
    CACHE_HIT = Counter("cache_hits_total", "Cache hits")
    CACHE_MISS = Counter("cache_misses_total", "Cache misses")
    YOUTUBE_API_CALLS = Counter("youtube_api_calls_total", "YouTube API calls", ["endpoint"])
    YOUTUBE_QUOTA_USED = Counter("youtube_quota_used_total", "YouTube API quota units consumed")
    ACTIVE_WEBSOCKETS = Gauge("active_websockets", "Number of active WebSocket connections")
    DISK_CACHE_SIZE = Gauge("disk_cache_size_bytes", "Disk cache size in bytes")


def init_sentry(dsn: str | None = None) -> None:
    """Initialize Sentry error tracking."""
    if not SENTRY_AVAILABLE:
        log.warning("Sentry SDK not available, skipping initialization")
        return

    dsn = dsn or os.getenv("SENTRY_DSN")
    if not dsn:
        log.info("SENTRY_DSN not set, skipping Sentry initialization")
        return

    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR,
    )

    sentry_sdk.init(
        dsn=dsn,
        integrations=[FastApiIntegration(), sentry_logging],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
    )
    log.info("Sentry initialized successfully")


async def health_check() -> Dict[str, Any]:
    """Comprehensive health check."""
    checks = {
        "status": "healthy",
        "timestamp": time.time(),
        "checks": {},
    }

    # Check database
    try:
        from services.db import db
        if db:
            await db.get_stats()
            checks["checks"]["database"] = {"status": "ok"}
        else:
            checks["checks"]["database"] = {"status": "not_initialized"}
    except Exception as e:
        checks["checks"]["database"] = {"status": "error", "error": str(e)}
        checks["status"] = "degraded"

    # Check disk cache
    try:
        from core.config_manager import config_manager
        if config_manager.config:
            data_dir = os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")
            cache_size = 0
            if os.path.exists(data_dir):
                for root, _, files in os.walk(data_dir):
                    for f in files:
                        cache_size += os.path.getsize(os.path.join(root, f))
            checks["checks"]["disk_cache"] = {
                "status": "ok",
                "size_bytes": cache_size,
            }
            if PROMETHEPUS_AVAILABLE:
                DISK_CACHE_SIZE.set(cache_size)
        else:
            checks["checks"]["disk_cache"] = {"status": "not_initialized"}
    except Exception as e:
        checks["checks"]["disk_cache"] = {"status": "error", "error": str(e)}
        checks["status"] = "degraded"

    # Check YouTube service
    try:
        from app import youtube_service
        if youtube_service:
            checks["checks"]["youtube_service"] = {"status": "ok"}
        else:
            checks["checks"]["youtube_service"] = {"status": "not_initialized"}
    except Exception as e:
        checks["checks"]["youtube_service"] = {"status": "error", "error": str(e)}

    return checks


async def readiness_check() -> Dict[str, Any]:
    """Check if the app is ready to serve requests."""
    try:
        from core.config_manager import config_manager
        if not config_manager.config:
            return {"status": "not_ready", "reason": "Configuration not loaded"}

        data_dir = os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")
        if not os.path.exists(data_dir):
            return {"status": "not_ready", "reason": "Data directory not accessible"}

        return {"status": "ready"}
    except Exception as e:
        return {"status": "not_ready", "reason": str(e)}


async def liveness_check() -> Dict[str, Any]:
    """Check if the app process is alive."""
    return {"status": "alive", "timestamp": time.time()}


def metrics_endpoint():
    """Prometheus metrics endpoint."""
    if not PROMETHEUS_AVAILABLE:
        return JSONResponse({"error": "Prometheus not available"}, status_code=503)

    return JSONResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_PROMETHEUS,
    )


class MetricsMiddleware:
    """Middleware to track HTTP request metrics."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]

        start_time = time.time()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
                if PROMETHEUS_AVAILABLE:
                    REQUEST_COUNT.labels(method=method, endpoint=path, status=status_code).inc()
                    REQUEST_DURATION.labels(method=method, endpoint=path).observe(time.time() - start_time)
            await send(message)

        await self.app(scope, receive, send_wrapper)