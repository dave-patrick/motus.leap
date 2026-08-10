"""Caching layer for motus.leap.

Provides multi-layer caching with Redis (distributed) and in-memory LRU cache.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Callable, Optional, TypeVar

from cachetools import TTLCache, LRUCache

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# In-Memory Caches
# ---------------------------------------------------------------------------

# LRU cache for frequently accessed data (no TTL)
_memory_lru: LRUCache = LRUCache(maxsize=1000)

# TTL cache for data that expires
_memory_ttl: TTLCache = TTLCache(maxsize=2000, ttl=300)  # 5-minute default TTL

# ---------------------------------------------------------------------------
# Redis Cache (Optional)
# ---------------------------------------------------------------------------

_redis_available = False
_redis_client = None
_redis_url = os.getenv("REDIS_URL", "")


def _get_redis():
    """Get or create Redis client."""
    global _redis_client, _redis_available

    if not _redis_url:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        import redis.asyncio as redis

        _redis_client = redis.from_url(_redis_url, decode_responses=True)
        _redis_available = True
        logger.info("Redis cache connected successfully")
        return _redis_client
    except ImportError:
        logger.warning("redis package not installed, using in-memory cache only")
        return None
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {e}")
        return None


async def _redis_get(key: str) -> Optional[str]:
    """Get value from Redis."""
    if not _redis_available:
        return None

    redis = _get_redis()
    if redis is None:
        return None

    try:
        return await redis.get(key)
    except Exception as e:
        logger.warning(f"Redis GET error for key '{key}': {e}")
        return None


async def _redis_set(key: str, value: str, ttl: int = 300) -> bool:
    """Set value in Redis with TTL."""
    if not _redis_available:
        return False

    redis = _get_redis()
    if redis is None:
        return False

    try:
        await redis.setex(key, ttl, value)
        return True
    except Exception as e:
        logger.warning(f"Redis SET error for key '{key}': {e}")
        return False


async def _redis_delete(key: str) -> bool:
    """Delete key from Redis."""
    if not _redis_available:
        return False

    redis = _get_redis()
    if redis is None:
        return False

    try:
        await redis.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Redis DELETE error for key '{key}': {e}")
        return False


# ---------------------------------------------------------------------------
# Cache Keys
# ---------------------------------------------------------------------------

def _make_key(prefix: str, *parts) -> str:
    """Create a cache key from prefix and parts."""
    return f"{prefix}:{':'.join(str(p) for p in parts)}"


# ---------------------------------------------------------------------------
# Public Cache API
# ---------------------------------------------------------------------------

async def get_cached(
    prefix: str,
    key_parts: tuple,
    ttl: int = 300,
    use_lru: bool = True,
) -> Optional[Any]:
    """Get a value from cache (Redis first, then in-memory).

    Args:
        prefix: Cache key prefix (e.g., 'youtube', 'playlists')
        key_parts: Parts to construct the cache key
        ttl: Time-to-live in seconds
        use_lru: Whether to also check the LRU cache

    Returns:
        Cached value or None if not found
    """
    key = _make_key(prefix, *key_parts)

    # Check Redis first (distributed cache)
    redis_value = await _redis_get(key)
    if redis_value is not None:
        try:
            return json.loads(redis_value)
        except (json.JSONDecodeError, TypeError):
            return redis_value

    # Check in-memory LRU cache
    if use_lru and key in _memory_lru:
        return _memory_lru[key]

    # Check in-memory TTL cache
    if key in _memory_ttl:
        return _memory_ttl[key]

    return None


async def set_cached(
    prefix: str,
    key_parts: tuple,
    value: Any,
    ttl: int = 300,
    use_lru: bool = True,
) -> bool:
    """Set a value in cache (Redis and in-memory).

    Args:
        prefix: Cache key prefix
        key_parts: Parts to construct the cache key
        value: Value to cache
        ttl: Time-to-live in seconds
        use_lru: Whether to also store in LRU cache

    Returns:
        True if stored in Redis, False otherwise
    """
    key = _make_key(prefix, *key_parts)

    # Serialize value for Redis
    try:
        serialized = json.dumps(value, default=str)
    except (TypeError, ValueError):
        serialized = str(value)

    # Store in Redis
    redis_success = await _redis_set(key, serialized, ttl)

    # Store in in-memory caches
    if use_lru:
        _memory_lru[key] = value
    _memory_ttl[key] = value

    return redis_success


async def delete_cached(
    prefix: str,
    key_parts: tuple,
    use_lru: bool = True,
) -> bool:
    """Delete a value from cache.

    Args:
        prefix: Cache key prefix
        key_parts: Parts to construct the cache key
        use_lru: Whether to also delete from LRU cache

    Returns:
        True if deleted from Redis, False otherwise
    """
    key = _make_key(prefix, *key_parts)

    # Delete from Redis
    redis_success = await _redis_delete(key)

    # Delete from in-memory caches
    if use_lru and key in _memory_lru:
        del _memory_lru[key]
    if key in _memory_ttl:
        del _memory_ttl[key]

    return redis_success


async def invalidate_pattern(pattern: str) -> int:
    """Invalidate all cache keys matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., 'youtube:playlists:*')

    Returns:
        Number of keys deleted
    """
    if not _redis_available:
        return 0

    redis = _get_redis()
    if redis is None:
        return 0

    try:
        keys = await redis.keys(pattern)
        if keys:
            return await redis.delete(*keys)
        return 0
    except Exception as e:
        logger.warning(f"Redis pattern invalidation error for '{pattern}': {e}")
        return 0


# ---------------------------------------------------------------------------
# Cache Decorator
# ---------------------------------------------------------------------------

def cached(
    prefix: str,
    ttl: int = 300,
    key_builder: Optional[Callable] = None,
    use_lru: bool = True,
):
    """Decorator for caching async function results.

    Args:
        prefix: Cache key prefix
        ttl: Time-to-live in seconds
        key_builder: Optional function to build cache key from args
        use_lru: Whether to also use LRU cache

    Example:
        @cached('youtube', ttl=600)
        async def get_playlists(user_id: str):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                key_parts = key_builder(*args, **kwargs)
            else:
                # Default: use positional args (skip self)
                key_parts = tuple(str(arg) for arg in args[1:])

            cache_key = _make_key(prefix, *key_parts)

            # Try to get from cache
            cached_value = await get_cached(prefix, key_parts, ttl, use_lru)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            await set_cached(prefix, key_parts, result, ttl, use_lru)

            return result

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Cache Warming
# ---------------------------------------------------------------------------

async def warm_cache(
    prefix: str,
    key_parts: tuple,
    fetch_func: Callable,
    ttl: int = 300,
) -> bool:
    """Pre-populate cache with fresh data.

    Args:
        prefix: Cache key prefix
        key_parts: Parts to construct the cache key
        fetch_func: Async function to fetch fresh data
        ttl: Time-to-live in seconds

    Returns:
        True if cache was warmed successfully
    """
    try:
        fresh_data = await fetch_func()
        await set_cached(prefix, key_parts, fresh_data, ttl)
        logger.info(f"Cache warmed for key: {_make_key(prefix, *key_parts)}")
        return True
    except Exception as e:
        logger.warning(f"Failed to warm cache for key: {_make_key(prefix, *key_parts)}: {e}")
        return False


# ---------------------------------------------------------------------------
# Cache Statistics
# ---------------------------------------------------------------------------

def get_cache_stats() -> dict:
    """Get cache statistics."""
    return {
        "memory_lru": {
            "current_size": len(_memory_lru),
            "max_size": _memory_lru.maxsize,
        },
        "memory_ttl": {
            "current_size": len(_memory_ttl),
            "max_size": _memory_ttl.maxsize,
            "ttl_seconds": _memory_ttl.ttl,
        },
        "redis": {
            "available": _redis_available,
            "connected": _redis_client is not None,
        },
    }


# ---------------------------------------------------------------------------
# Cache Clearing
# ---------------------------------------------------------------------------

async def clear_all_caches() -> dict:
    """Clear all caches and return statistics."""
    # Clear in-memory caches
    lru_size = len(_memory_lru)
    ttl_size = len(_memory_ttl)
    _memory_lru.clear()
    _memory_ttl.clear()

    # Clear Redis cache
    redis_cleared = 0
    if _redis_available and _redis_client is not None:
        try:
            redis_cleared = await _redis_client.flushdb()
        except Exception as e:
            logger.warning(f"Failed to clear Redis cache: {e}")

    return {
        "memory_lru_cleared": lru_size,
        "memory_ttl_cleared": ttl_size,
        "redis_cleared": redis_cleared,
    }


# Initialize Redis on module load
def _init_redis():
    """Initialize Redis connection on module load."""
    global _redis_available
    _get_redis()


# Try to initialize Redis
_init_redis()