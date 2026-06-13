"""HTTP client with connection pooling and HTTP/2 support."""

import httpx
from httpx import AsyncClient, Limits, Timeout
from typing import Optional
import logging

log = logging.getLogger(__name__)

# Global HTTP client instance
_http_client: Optional[AsyncClient] = None


def get_http_client() -> AsyncClient:
    """Get or create HTTP client with pooling.

    Returns:
        AsyncClient with connection pooling and HTTP/2 support
    """
    global _http_client
    if _http_client is None:
        _http_client = AsyncClient(
            limits=Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=30.0,
            ),
            timeout=Timeout(30.0, connect=5.0),
            http2=True,  # HTTP/2 multiplexing
        )
        log.info("HTTP client initialized with pooling and HTTP/2")
    return _http_client


async def shutdown_http_client():
    """Close HTTP client gracefully."""
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
        log.info("HTTP client shutdown complete")
