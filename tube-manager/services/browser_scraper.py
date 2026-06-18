"""Browser-based scraping service for YouTube Watch Later.
Uses Playwright + Camoufox to bypass YouTube API restrictions on native Watch Later access."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Lazy imports to avoid crashes if Playwright isn't available on the server
PLAYWRIGHT_AVAILABLE = False
CAMOUFOX_AVAILABLE = False

try:
    from camoufox import Camoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    try:
        from playwright.sync_api import sync_playwright
        PLAYWRIGHT_AVAILABLE = True
    except ImportError:
        pass

COOKIES_DIR = Path(__file__).parent.parent / "data"


def _cookies_path() -> Path:
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    return COOKIES_DIR / "youtube_cookies.json"


def has_cookies() -> bool:
    """Check if YouTube browser cookies are saved."""
    cp = _cookies_path()
    if not cp.exists():
        return False
    try:
        with open(cp) as f:
            cookies = json.load(f)
        return len(cookies) > 0
    except (json.JSONDecodeError, OSError):
        return False


def scrape_watch_later_videos(max_items: int = 200) -> dict:
    """Scrape the native YouTube Watch Later playlist using a headless browser.
    
    Returns dict with 'items' list (same format as YouTube API playlistItems).
    Falls back gracefully if browser not available or cookies not found.
    """
    if not has_cookies():
        log.warning("[BROWSER] No YouTube cookies found. Cannot scrape Watch Later via browser.")
        return {"items": [], "error": "cookies_missing", "message": "Export YouTube cookies to continue."}
    
    if not CAMOUFOX_AVAILABLE and not PLAYWRIGHT_AVAILABLE:
        log.warning("[BROWSER] Neither Camoufox nor Playwright is installed.")
        return {"items": [], "error": "browser_unavailable"}
    
    cookies_path = _cookies_path()
    
    try:
        if CAMOUFOX_AVAILABLE:
            return _scrape_with_camoufox(cookies_path, max_items)
        else:
            return _scrape_with_playwright(cookies_path, max_items)
    except Exception as e:
        log.error(f"[BROWSER] Scraping failed: {e}")
        return {"items": [], "error": str(e)}


def _sanitize_cookies(cookies: list[dict]) -> list[dict]:
    """Sanitize exported browser cookies for Playwright/Camoufox compatibility."""
    sanitized = []
    for c in cookies:
        sc = dict(c)
        # Playwright expects "Strict", "Lax", or "None"
        if sc.get("sameSite") in ("no_restriction", None, ""):
            sc["sameSite"] = "None"
        elif sc.get("sameSite") not in ("Strict", "Lax", "None"):
            sc["sameSite"] = "Lax"
        # Remove fields Playwright doesn't accept
        sc.pop("storeId", None)
        sc.pop("hostOnly", None)
        sc.pop("session", None)
        # Ensure required fields
        if "name" in sc and "value" in sc and "domain" in sc:
            if "path" not in sc or not sc.get("path"):
                sc["path"] = "/"
            sanitized.append(sc)
    return sanitized


def _scrape_with_camoufox(cookies_path: Path, max_items: int) -> dict:
    """Use Camoufox (stealth browser) to scrape Watch Later."""
    log.info("[BROWSER] Launching Camoufox browser...")
    
    items = []
    with Camoufox(headless=True) as browser:
        context = browser.new_context()
        
        # Load saved cookies
        with open(cookies_path) as f:
            cookies = _sanitize_cookies(json.load(f))
        context.add_cookies(cookies)
        
        page = context.new_page()
        page.goto("https://www.youtube.com/playlist?list=WL", wait_until="networkidle")
        
        # Scroll to load more videos
        for _ in range(5):
            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            page.wait_for_timeout(2000)
        
        # Extract video data from the rendered page
        video_elements = page.query_selector_all("ytd-playlist-video-renderer")
        for el in video_elements:
            if len(items) >= max_items:
                break
            try:
                title_el = el.query_selector("#video-title")
                video_id = None
                if title_el:
                    href = title_el.get_attribute("href") or ""
                    if "v=" in href:
                        video_id = href.split("v=")[1].split("&")[0]
                
                if not video_id:
                    continue
                    
                title = title_el.text_content().strip() if title_el else "Unknown"
                channel_el = el.query_selector("#channel-name a")
                channel_title = channel_el.text_content().strip() if channel_el else ""
                channel_id = ""
                if channel_el:
                    ch_href = channel_el.get_attribute("href") or ""
                    if "/channel/" in ch_href:
                        channel_id = ch_href.split("/channel/")[1].split("/")[0]
                
                # Build data that matches our api format
                item = {
                    "id": video_id,
                    "snippet": {
                        "title": title,
                        "videoOwnerChannelId": channel_id,
                        "videoOwnerChannelTitle": channel_title,
                        "playlistId": "WL",
                    },
                    "contentDetails": {
                        "videoId": video_id,
                    }
                }
                items.append(item)
            except Exception:
                continue
        
        context.close()
    
    log.info(f"[BROWSER] Scraped {len(items)} videos from Watch Later")
    return {"items": items}


def _scrape_with_playwright(cookies_path: Path, max_items: int) -> dict:
    """Fallback: Use plain Playwright (no stealth) to scrape Watch Later."""
    log.info("[BROWSER] Launching Playwright browser (fallback mode)...")
    
    items = []
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        
        with open(cookies_path) as f:
            cookies = _sanitize_cookies(json.load(f))
        context.add_cookies(cookies)
        
        page = context.new_page()
        page.goto("https://www.youtube.com/playlist?list=WL", wait_until="networkidle")
        
        for _ in range(5):
            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            page.wait_for_timeout(2000)
        
        video_elements = page.query_selector_all("ytd-playlist-video-renderer")
        for el in video_elements:
            if len(items) >= max_items:
                break
            try:
                title_el = el.query_selector("#video-title")
                video_id = None
                if title_el:
                    href = title_el.get_attribute("href") or ""
                    if "v=" in href:
                        video_id = href.split("v=")[1].split("&")[0]
                if not video_id:
                    continue
                title = title_el.text_content().strip() if title_el else "Unknown"
                channel_el = el.query_selector("#channel-name a")
                channel_title = channel_el.text_content().strip() if channel_el else ""
                channel_id = ""
                if channel_el:
                    ch_href = channel_el.get_attribute("href") or ""
                    if "/channel/" in ch_href:
                        channel_id = ch_href.split("/channel/")[1].split("/")[0]
                item = {
                    "id": video_id,
                    "snippet": {
                        "title": title,
                        "videoOwnerChannelId": channel_id,
                        "videoOwnerChannelTitle": channel_title,
                        "playlistId": "WL",
                    },
                    "contentDetails": {"videoId": video_id},
                }
                items.append(item)
            except Exception:
                continue
        
        context.close()
        browser.close()
    
    log.info(f"[BROWSER] Scraped {len(items)} videos from Watch Later")
    return {"items": items}
