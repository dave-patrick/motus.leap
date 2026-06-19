"""LRU cache with async operations and eviction policy."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

log = logging.getLogger(__name__)


class LRUAsyncCache:
    """LRU cache with async cleanup and TTL support.

    Features:
    - Max size enforcement with LRU eviction
    - Time-based expiration (TTL)
    - Thread-safe operations via asyncio.Lock
    - Access tracking for eviction decisions
    """

    def __init__(self, max_size: int = 100, ttl: timedelta = timedelta(minutes=10)):
        """Initialize LRU cache.

        Args:
            max_size: Maximum number of items to cache
            ttl: Time-to-live for cache entries
        """
        self._cache: Dict[str, Any] = {}
        self._expires_at: Dict[str, datetime] = {}
        self._access_count: Dict[str, int] = {}
        self._max_size = max_size
        self._ttl = ttl
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/missing
        """
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            # Check TTL
            if datetime.now() > self._expires_at[key]:
                await self._evict(key)
                self._misses += 1
                return None

            # Update access for LRU
            self._access_count[key] = self._access_count.get(key, 0) + 1
            self._hits += 1
            await self._maybe_evict()
            return self._cache[key]

    async def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """Set cached value.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional, per-item time-to-live. If not provided, uses the cache's default TTL.
        """
        async with self._lock:
            self._cache[key] = value
            self._expires_at[key] = datetime.now() + (ttl or self._ttl)
            self._access_count[key] = 0
            await self._maybe_evict()

    async def _maybe_evict(self) -> None:
        """Evict least recently used if at capacity."""
        if len(self._cache) >= self._max_size:
            # Sort by access count, evict lowest
            if self._access_count:
                lru_key = min(self._access_count, key=self._access_count.get)
                await self._evict(lru_key)
                log.debug(f"LRU evicted: {lru_key}")

    async def _evict(self, key: str) -> None:
        """Remove entry from cache."""
        self._cache.pop(key, None)
        self._expires_at.pop(key, None)
        self._access_count.pop(key, None)

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._expires_at.clear()
            self._access_count.clear()
            log.info("LRU cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with hit rate, size, etc.
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2%}",
            "ttl_seconds": int(self._ttl.total_seconds()),
        }
