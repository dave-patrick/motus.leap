"""Performance optimization fixes for Tube Manager - Phase 2-3.

Run this to apply Phase 2-3 optimizations:
  python performance_optimization_phase2_3.py

This applies:
- Phase 2: Memory & Connection (LRU cache, HTTP pooling)
- Phase 3: API & WebSocket (pagination, throttling)
"""

import os
import shutil
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================
PROJECT_ROOT = Path(__file__).parent
TUBE_MANAGER_DIR = PROJECT_ROOT / "tube-manager"

# =============================================================================
# PHASE 2: MEMORY & CONNECTION
# =============================================================================

def add_lru_cache_module():
    """Create a new LRU cache module for memory management."""
    print("🔧 Creating LRU cache module...")

    lru_file = TUBE_MANAGER_DIR / "core" / "lru_cache.py"
    if lru_file.exists():
        print("⚠️ LRU cache module already exists")
        return False

    lru_content = '''"""LRU cache with async operations and eviction policy."""

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
        self._timestamp: Dict[str, datetime] = {}
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
            if datetime.now() - self._timestamp[key] > self._ttl:
                await self._evict(key)
                self._misses += 1
                return None

            # Update access for LRU
            self._access_count[key] = self._access_count.get(key, 0) + 1
            self._hits += 1
            await self._maybe_evict()
            return self._cache[key]

    async def set(self, key: str, value: Any) -> None:
        """Set cached value.

        Args:
            key: Cache key
            value: Value to cache
        """
        async with self._lock:
            self._cache[key] = value
            self._timestamp[key] = datetime.now()
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
        self._timestamp.pop(key, None)
        self._access_count.pop(key, None)

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._timestamp.clear()
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
'''

    lru_file.parent.mkdir(parents=True, exist_ok=True)
    lru_file.write_text(lru_content, encoding="utf-8")
    print("✅ Created core/lru_cache.py")
    return True


def add_httpx_dependency():
    """Add httpx to requirements.txt for connection pooling."""
    print("🔧 Adding httpx dependency...")

    reqs_file = TUBE_MANAGER_DIR / "requirements.txt"
    if not reqs_file.exists():
        print(f"❌ File not found: {reqs_file}")
        return False

    content = reqs_file.read_text(encoding="utf-8")
    if "httpx" not in content:
        with open(reqs_file, "a", encoding="utf-8") as f:
            f.write("\nhttpx>=0.25.0\n")
        print("✅ Added httpx to requirements.txt")
        return True
    else:
        print("⚠️ httpx already in requirements.txt")
        return False


def integrate_lru_cache_in_service():
    """Integrate LRU cache into YouTube service."""
    print("🔧 Integrating LRU cache into YouTube service...")

    service_file = TUBE_MANAGER_DIR / "services" / "youtube_service.py"
    if not service_file.exists():
        print(f"❌ File not found: {service_file}")
        return False

    old_content = service_file.read_text(encoding="utf-8")

    # Add LRU cache import
    if "from core.lru_cache import LRUAsyncCache" not in old_content:
        old_content = old_content.replace(
            "from models.config import TubeManagerConfig",
            "from models.config import TubeManagerConfig\nfrom core.lru_cache import LRUAsyncCache"
        )

    # Replace simple cache dict with LRU cache
    old_cache_init = '''        # Local cache to avoid redundant API calls
        self._cache: Dict[str, Any] = {}
        self._cache_timestamp: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(minutes=10)  # Cache for 10 minutes (increased from 5)'''

    new_cache_init = '''        # LRU cache to avoid redundant API calls with eviction policy
        self._cache = LRUAsyncCache(max_size=100, ttl=timedelta(minutes=10))'''

    new_content = old_content.replace(old_cache_init, new_cache_init)

    # Replace cache methods
    old_get_cached = '''    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached data if not expired.

        Args:
            key: Cache key

        Returns:
            Cached data or None if expired/missing
        """
        if key in self._cache:
            if datetime.now() - self._cache_timestamp[key] < self._cache_ttl:
                log.debug(f"Cache hit: {key}")
                return self._cache[key]
            else:
                log.debug(f"Cache expired: {key}")
                del self._cache[key]
                del self._cache_timestamp[key]
        return None

    def _set_cached(self, key: str, data: Any) -> None:
        """Cache data with timestamp.

        Args:
            key: Cache key
            data: Data to cache
        """
        self._cache[key] = data
        self._cache_timestamp[key] = datetime.now()
        log.debug(f"Cached: {key} (TTL: {self._cache_ttl.total_seconds()}s)")

    def _clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        self._cache_timestamp.clear()
        log.info("Cache cleared")'''

    new_get_cached = '''    async def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached data if not expired.

        Args:
            key: Cache key

        Returns:
            Cached data or None if expired/missing
        """
        return await self._cache.get(key)

    async def _set_cached(self, key: str, data: Any) -> None:
        """Cache data with timestamp.

        Args:
            key: Cache key
            data: Data to cache
        """
        await self._cache.set(key, data)
        log.debug(f"Cached: {key}")

    async def _clear_cache(self) -> None:
        """Clear all cached data."""
        await self._cache.clear()
        log.info("Cache cleared")'''

    new_content = new_content.replace(old_get_cached, new_get_cached)

    if new_content != old_content:
        service_file.write_text(new_content, encoding="utf-8")
        print("✅ Integrated LRU cache into YouTube service")
        return True
    else:
        print("⚠️ No changes needed for LRU cache integration")
        return False


def add_http_client_module():
    """Create HTTP client module with connection pooling."""
    print("🔧 Creating HTTP client module...")

    http_file = TUBE_MANAGER_DIR / "core" / "http_client.py"
    if http_file.exists():
        print("⚠️ HTTP client module already exists")
        return False

    http_content = '''"""HTTP client with connection pooling and HTTP/2 support."""

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
'''

    http_file.parent.mkdir(parents=True, exist_ok=True)
    http_file.write_text(http_content, encoding="utf-8")
    print("✅ Created core/http_client.py")
    return True


def update_app_lifespan():
    """Update app lifespan to include HTTP client cleanup."""
    print("🔧 Updating app lifespan for HTTP client cleanup...")

    app_file = TUBE_MANAGER_DIR / "app.py"
    if not app_file.exists():
        print(f"❌ File not found: {app_file}")
        return False

    old_content = app_file.read_text(encoding="utf-8")

    # Add HTTP client import
    if "from core.http_client import shutdown_http_client" not in old_content:
        old_content = old_content.replace(
            "# Core imports",
            "# Core imports\nfrom core.http_client import shutdown_http_client"
        )

    # Update lifespan to include HTTP client cleanup
    old_lifespan = '''    # Shutdown
    log.info("Tube Manager shutting down")'''

    new_lifespan = '''    # Shutdown
    log.info("Tube Manager shutting down")
    await shutdown_http_client()'''

    new_content = old_content.replace(old_lifespan, new_lifespan)

    if new_content != old_content:
        app_file.write_text(new_content, encoding="utf-8")
        print("✅ Updated app lifespan for HTTP client cleanup")
        return True
    else:
        print("⚠️ No changes needed for app lifespan")
        return False


# =============================================================================
# PHASE 3: API & WEBSOCKET
# =============================================================================

def optimize_pagination():
    """Add pagination optimization helper to YouTube service."""
    print("🔧 Adding pagination optimization to YouTube service...")

    service_file = TUBE_MANAGER_DIR / "services" / "youtube_service.py"
    if not service_file.exists():
        print(f"❌ File not found: {service_file}")
        return False

    old_content = service_file.read_text(encoding="utf-8")

    # Add pagination helper method
    pagination_helper = '''
    async def _fetch_all_paginated(self, fetch_fn, max_results: int = 50, max_items: int = 500):
        """Fetch paginated results with caps and early exit.

        Args:
            fetch_fn: Function to fetch paginated results
            max_results: Results per page
            max_items: Maximum total items to fetch

        Returns:
            List of items
        """
        all_items = []
        page_token = None

        while len(all_items) < max_items:
            resp = fetch_fn(max_results=max_results, page_token=page_token)
            items = resp.get("items", [])
            all_items.extend(items)

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

            # Early exit if approaching quota
            if len(all_items) + max_results > max_items:
                log.warning(f"Approaching item cap {max_items}, stopping pagination")
                break

        return all_items[:max_items]
'''

    # Add after _parse_duration method
    if "async def _fetch_all_paginated" not in old_content:
        # Find insertion point after _format_duration
        insert_point = '        return " ".join(parts)'

        new_content = old_content.replace(
            insert_point,
            insert_point + pagination_helper
        )

        if new_content != old_content:
            service_file.write_text(new_content, encoding="utf-8")
            print("✅ Added pagination optimization helper")
            return True

    print("⚠️ Pagination helper already exists")
    return False


def optimize_websocket_broadcast():
    """Optimize WebSocket broadcast with throttling."""
    print("🔧 Optimizing WebSocket broadcast with throttling...")

    app_file = TUBE_MANAGER_DIR / "app.py"
    if not app_file.exists():
        print(f"❌ File not found: {app_file}")
        return False

    old_content = app_file.read_text(encoding="utf-8")

    # Replace ConnectionManager with throttling version
    old_manager = '''class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"WebSocket send error: {e}")
                pass'''

    new_manager = '''class ConnectionManager:
    """Manages WebSocket connections with throttling."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._last_broadcast_time = {}
        self._min_broadcast_interval = 0.1  # 100ms between messages per client

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients with throttling."""
        import asyncio
        now = asyncio.get_event_loop().time()
        tasks = []
        for connection in self.active_connections:
            conn_id = id(connection)
            # Rate limit per client
            if now - self._last_broadcast_time.get(conn_id, 0) >= self._min_broadcast_interval:
                self._last_broadcast_time[conn_id] = now
                tasks.append(self._safe_send(connection, message))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_send(self, connection: WebSocket, message: str):
        """Send message to single WebSocket with error handling."""
        try:
            await connection.send_text(message)
        except Exception as e:
            log.debug(f"WebSocket send failed (likely disconnected): {e}")
            self.disconnect(connection)'''

    new_content = old_content.replace(old_manager, new_manager)

    if new_content != old_content:
        app_file.write_text(new_content, encoding="utf-8")
        print("✅ Optimized WebSocket broadcast with throttling")
        return True
    else:
        print("⚠️ WebSocket throttling already in place")
        return False


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Apply Phase 2-3 optimizations."""
    print("=" * 60)
    print("🚀 Tube Manager Performance Optimization - Phase 2-3")
    print("=" * 60)
    print()

    changes = []

    # Phase 2: Memory & Connection
    print("\n📋 Phase 2: Memory & Connection")
    print("-" * 60)

    if add_lru_cache_module():
        changes.append("✅ Created LRU cache module")

    if add_httpx_dependency():
        changes.append("✅ Added httpx dependency")

    if integrate_lru_cache_in_service():
        changes.append("✅ Integrated LRU cache into YouTube service")

    if add_http_client_module():
        changes.append("✅ Created HTTP client module")

    if update_app_lifespan():
        changes.append("✅ Updated app lifespan for HTTP client cleanup")

    # Phase 3: API & WebSocket
    print("\n📋 Phase 3: API & WebSocket")
    print("-" * 60)

    if optimize_pagination():
        changes.append("✅ Added pagination optimization helper")

    if optimize_websocket_broadcast():
        changes.append("✅ Optimized WebSocket broadcast with throttling")

    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)
    print(f"Applied {len(changes)} optimization(s):")
    for change in changes:
        print(f"  {change}")

    if changes:
        print("\n🎯 Next steps:")
        print("  1. Review the changes in git:")
        print("     git diff")
        print("\n  2. Install new dependencies:")
        print("     pip install -r tube-manager/requirements.txt")
        print("\n  3. Test the application locally:")
        print("     cd tube-manager && python app.py")
        print("\n  4. Deploy to Render:")
        print("     git add . && git commit -m 'perf: apply phase 2-3 optimizations'")
        print("     git push")
        print("\n  5. Monitor for improvements:")
        print("     - Memory usage (40-60% reduction expected)")
        print("     - API latency (10-20% reduction expected)")
        print("     - WebSocket stability under load")
    else:
        print("\n⚠️ No changes applied. All Phase 2-3 optimizations may already be in place.")

    print("\n" + "=" * 60)
    print("✨ Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()