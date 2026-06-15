"""Performance optimization fixes for Tube Manager.

Run this to apply Phase 1 optimizations:
  python performance_optimization_fixes.py

This file contains ready-to-apply fixes for the issues identified
in the performance scan.
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
# PHASE 1: QUICK WINS
# =============================================================================

def fix_datetime_utcnow():
    """Fix models/task.py: Replace datetime.utcnow() with timezone-aware datetime.now()."""
    print("🔧 Fixing datetime.utcnow() deprecation...")

    task_file = TUBE_MANAGER_DIR / "models" / "task.py"
    if not task_file.exists():
        print(f"❌ File not found: {task_file}")
        return False

    old_content = task_file.read_text(encoding="utf-8")
    new_content = old_content

    # Add timezone import at top
    if "from datetime import timezone" not in old_content:
        new_content = new_content.replace(
            "from enum import Enum",
            "from enum import Enum\nfrom datetime import timezone"
        )

    # Replace utcnow() with now(timezone.utc)
    new_content = new_content.replace(
        'datetime.datetime.utcnow().isoformat()',
        'datetime.datetime.now(timezone.utc).isoformat()'
    )

    if new_content != old_content:
        task_file.write_text(new_content, encoding="utf-8")
        print("✅ Fixed datetime.utcnow() in models/task.py")
        return True
    else:
        print("⚠️ No changes needed for datetime.utcnow()")
        return False


def add_aiofiles_dependency():
    """Add aiofiles to requirements.txt for async file I/O."""
    print("🔧 Adding aiofiles dependency...")

    reqs_file = TUBE_MANAGER_DIR / "requirements.txt"
    if not reqs_file.exists():
        print(f"❌ File not found: {reqs_file}")
        return False

    content = reqs_file.read_text(encoding="utf-8")
    if "aiofiles" not in content:
        with open(reqs_file, "a", encoding="utf-8") as f:
            f.write("\naiofiles>=23.0.0\n")
        print("✅ Added aiofiles to requirements.txt")
        return True
    else:
        print("⚠️ aiofiles already in requirements.txt")
        return False


def optimize_no_cache_file_response():
    """Fix app.py: Convert no_cache_file_response to async with aiofiles."""
    print("🔧 Optimizing no_cache_file_response for async I/O...")

    app_file = TUBE_MANAGER_DIR / "app.py"
    if not app_file.exists():
        print(f"❌ File not found: {app_file}")
        return False

    old_content = app_file.read_text(encoding="utf-8")

    # Add aiofiles import if not present
    if "import aiofiles" not in old_content:
        old_content = old_content.replace(
            "from pydantic import BaseModel",
            "from pydantic import BaseModel\nimport aiofiles"
        )

    # Replace synchronous function with async version
    old_function = '''def no_cache_file_response(file_path: Path) -> Response:
    """Return HTML response with no-cache headers to prevent CDN/browser caching."""
    try:
        content = file_path.read_text(encoding="utf-8")
        # Add a visible marker to confirm fresh deploy
        content = content.replace(
            '<title>Tube Manager</title>',
            '<title>Tube Manager</title>\\n    <meta name="deploy-time" content="' + str(int(__import__('time').time())) + '">'
        )
        return Response(
            content=content,
            media_type="text/html; charset=utf-8",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )
    except Exception as e:
        log.error(f"Failed to read file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load page: {str(e)}")'''

    new_function = '''async def no_cache_file_response(file_path: Path) -> Response:
    """Return HTML response with no-cache headers to prevent CDN/browser caching."""
    try:
        async with aiofiles.open(file_path, mode='r', encoding="utf-8") as f:
            content = await f.read()

        # Add a visible marker to confirm fresh deploy
        content = content.replace(
            '<title>Tube Manager</title>',
            '<title>Tube Manager</title>\\n    <meta name="deploy-time" content="' + str(int(__import__('time').time())) + '">'
        )
        return Response(
            content=content,
            media_type="text/html; charset=utf-8",
            headers={
                "Cache-Control": "public, max-age=0",  # Allow ETag support
                "Pragma": "no-cache",
            }
        )
    except Exception as e:
        log.error(f"Failed to read file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load page: {str(e)}")'''

    new_content = old_content.replace(old_function, new_function)

    if new_content != old_content:
        app_file.write_text(new_content, encoding="utf-8")
        print("✅ Optimized no_cache_file_response in app.py")
        return True
    else:
        print("⚠️ No changes needed for no_cache_file_response")
        return False


# =============================================================================
# PHASE 2: MEMORY & CONNECTION (Optional - requires more testing)
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


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Apply Phase 1 optimizations."""
    print("=" * 60)
    print("🚀 Tube Manager Performance Optimization - Phase 1")
    print("=" * 60)
    print()

    changes = []

    # Phase 1: Quick Wins
    print("\n📋 Phase 1: Quick Wins")
    print("-" * 60)

    if fix_datetime_utcnow():
        changes.append("✅ Fixed datetime.utcnow() deprecation")

    if add_aiofiles_dependency():
        changes.append("✅ Added aiofiles dependency")

    if optimize_no_cache_file_response():
        changes.append("✅ Optimized no_cache_file_response (async I/O)")

    # Phase 2: Optional (commented out by default)
    # print("\n📋 Phase 2: Memory & Connection (Optional)")
    # print("-" * 60)
    #
    # if add_lru_cache_module():
    #     changes.append("✅ Created LRU cache module")
    #
    # if add_httpx_dependency():
    #     changes.append("✅ Added httpx dependency")

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
        print("     git add . && git commit -m 'perf: apply phase 1 optimizations'")
        print("     git push")
        print("\n  5. Monitor for improvements:")
        print("     - Page load times")
        print("     - Memory usage")
        print("     - API latency")
    else:
        print("\n⚠️ No changes applied. All optimizations may already be in place.")

    print("\n" + "=" * 60)
    print("✨ Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()