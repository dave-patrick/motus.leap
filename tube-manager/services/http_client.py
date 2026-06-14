"""HTTP client for external service communication."""

import logging
from typing import Any, Dict, Optional

import aiohttp

log = logging.getLogger(__name__)


class HTTPClient:
    """Async HTTP client wrapper."""

    def __init__(self, base_url: str = "", timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def get(self, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()

    async def post(self, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()


_client: Optional[HTTPClient] = None


def get_http_client() -> HTTPClient:
    global _client
    if _client is None:
        _client = HTTPClient()
    return _client


async def shutdown_http_client() -> None:
    global _client
    _client = None
