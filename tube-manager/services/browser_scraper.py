"""HTTPX-based YouTube Watch Later scraper using saved cookies.
Replaces Playwright/Camoufox — no browser binary needed.

Fetches the native Watch Later playlist via YouTube's InnerTube API
(youtubei.googleapis.com) using SAPISID-based auth from saved cookies."""

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)

COOKIES_DIR = Path(__file__).resolve().parent.parent / "data"


def _cookies_path() -> Path:
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    return COOKIES_DIR / "youtube_cookies.json"


def has_cookies() -> bool:
    """Check if YouTube browser cookies are saved."""
    cp = _cookies_path()
    if not cp.exists():
        log.warning("[HTTPX SCRAPER] Cookie file not found: %s", cp)
        return False
    try:
        with open(cp) as f:
            cookies = json.load(f)
        log.info("[HTTPX SCRAPER] Loaded %d cookies from %s", len(cookies), cp)
        return len(cookies) > 0
    except (json.JSONDecodeError, OSError):
        log.error("[HTTPX SCRAPER] Failed to read cookies from %s", cp)
        return False


def _load_cookies_raw() -> list[dict]:
    """Load raw cookie array from disk."""
    cp = _cookies_path()
    with open(cp) as f:
        return json.load(f)


def _build_cookie_header(cookies: list[dict]) -> str:
    """Build 'Cookie' header string from browser-cookie JSON array."""
    parts = []
    for c in cookies:
        name = c.get("name", "") or c.get("key", "")
        value = c.get("value", "")
        if name and value:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def _get_sapisid_hash(cookies: list[dict]) -> str:
    """Build SAPISIDHASH Authorization header value from SAPISID cookie.

    YouTube's internal API requires: SAPISIDHASH <timestamp>_<sha1(timestamp sapisid)>
    """
    sapisid = None
    for c in cookies:
        name = c.get("name", "") or c.get("key", "")
        if name in ("SAPISID", "__Secure-3PAPISID"):
            sapisid = c["value"]
            break
    if not sapisid:
        return ""
    timestamp = int(time.time())
    hash_input = f"{timestamp} {sapisid}"
    hash_val = hashlib.sha1(hash_input.encode()).hexdigest()
    return f"SAPISIDHASH {timestamp}_{hash_val}"


def _get_api_key_from_page(html: str) -> str:
    """Extract the INNERTUBE_API_KEY from YouTube page ytcfg data."""
    match = re.search(r'INNERTUBE_API_KEY["\']\s*:\s*["\']([^"\']+)["\']', html)
    if match:
        return match.group(1)
    # Try broader pattern
    match = re.search(r'innertubeApiKey["\']?\s*:\s*["\']([^"\']+)["\']', html)
    if match:
        return match.group(1)
    return ""


def _get_client_version(html: str) -> str:
    """Extract INNERTUBE_CLIENT_VERSION from YouTube page ytcfg data."""
    match = re.search(r'INNERTUBE_CLIENT_VERSION["\']\s*:\s*["\']([^"\']+)["\']', html)
    if match:
        return match.group(1)
    match = re.search(r'innertubeContextClientVersion["\']?\s*:\s*["\']([^"\']+)["\']', html)
    if match:
        return match.group(1)
    return "2.20240601.00.00"


def _extract_yt_initial_data(html: str) -> Optional[dict]:
    """Extract ytInitialData JSON from YouTube page HTML."""
    match = re.search(r'ytInitialData\s*=\s*({.*?});', html, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Fallback: try window['ytInitialData']
    match = re.search(r'window\[["\']ytInitialData["\']\]\s*=\s*({.*?});', html, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _extract_playlist_items_from_data(data: dict) -> list[dict]:
    """Extract video items from ytInitialData / InnerTube API response."""
    items = []

    # Try InnerTube API browse response format first
    contents = (
        data.get("contents", {})
        .get("twoColumnBrowseResultsRenderer", {})
        .get("tabs", [])
    )
    for tab in contents:
        tab_content = tab.get("tabRenderer", {}).get("content", {})
        section_list = tab_content.get("sectionListRenderer", {}).get("contents", [])
        for section in section_list:
            item_section = section.get("itemSectionRenderer", {}).get("contents", [])
            for item in item_section:
                pl_video_list = item.get("playlistVideoListRenderer", {}).get("contents", [])
                for video_entry in pl_video_list:
                    video_renderer = video_entry.get("playlistVideoRenderer", {})
                    if not video_renderer:
                        # Check for continuation token
                        cont = video_entry.get("continuationItemRenderer", {})
                        if cont:
                            continue  # handled separately
                        continue
                    video_id = video_renderer.get("videoId", "")
                    if not video_id:
                        continue
                    title_runs = video_renderer.get("title", {}).get("runs", [])
                    title = title_runs[0].get("text", "") if title_runs else ""
                    channel_runs = video_renderer.get("shortBylineText", {}).get("runs", [])
                    channel_title = channel_runs[0].get("text", "") if channel_runs else ""
                    channel_id = ""
                    if channel_runs:
                        ch_nav = channel_runs[0].get("navigationEndpoint", {})
                        ch_browse = ch_nav.get("browseEndpoint", {})
                        if ch_browse.get("browseId", "").startswith("UC"):
                            channel_id = ch_browse["browseId"]

                    thumbnails = video_renderer.get("thumbnail", {}).get("thumbnails", [])

                    items.append({
                        "id": video_id,
                        "snippet": {
                            "title": title,
                            "videoOwnerChannelId": channel_id,
                            "videoOwnerChannelTitle": channel_title,
                            "playlistId": "WL",
                        },
                        "contentDetails": {"videoId": video_id},
                        "thumbnails": thumbnails,
                    })

    return items


def _extract_continuation_token(data: dict) -> Optional[str]:
    """Extract continuation token for pagination from InnerTube response."""
    contents = (
        data.get("contents", {})
        .get("twoColumnBrowseResultsRenderer", {})
        .get("tabs", [])
    )
    for tab in contents:
        tab_content = tab.get("tabRenderer", {}).get("content", {})
        section_list = tab_content.get("sectionListRenderer", {}).get("contents", [])
        for section in section_list:
            item_section = section.get("itemSectionRenderer", {}).get("contents", [])
            for item in item_section:
                pl_video_list = item.get("playlistVideoListRenderer", {}).get("contents", [])
                for video_entry in reversed(pl_video_list):
                    cont = video_entry.get("continuationItemRenderer", {})
                    if cont:
                        token = (
                            cont.get("continuationEndpoint", {})
                            .get("continuationCommand", {})
                            .get("token")
                        )
                        if token:
                            return token
    # Also check 'onResponseReceivedEndpoints' for continuation
    on_response = data.get("onResponseReceivedEndpoints", [])
    for ep in on_response:
        append = ep.get("appendContinuationItemsAction", {})
        cont_items = append.get("continuationItems", [])
        for item in cont_items:
            cont = item.get("continuationItemRenderer", {})
            if cont:
                token = (
                    cont.get("continuationEndpoint", {})
                    .get("continuationCommand", {})
                    .get("token")
                )
                if token:
                    return token
    return None


def _fetch_continuation_page(
    client: httpx.Client,
    api_key: str,
    client_version: str,
    token: str,
    headers: dict,
) -> dict:
    """Fetch next page of results using a continuation token."""
    payload = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": client_version,
            }
        },
        "continuation": token,
    }
    url = f"https://www.youtube.com/youtubei/v1/browse?key={api_key}"
    resp = client.post(url, headers=headers, json=payload, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def _extract_continuation_items(data: dict) -> list[dict]:
    """Extract video items from a continuation page response."""
    items = []
    endpoints = data.get("onResponseReceivedEndpoints", [])
    for ep in endpoints:
        append = ep.get("appendContinuationItemsAction", {})
        cont_items = append.get("continuationItems", [])
        for item in cont_items:
            video_renderer = item.get("playlistVideoRenderer", {})
            if not video_renderer:
                continue
            video_id = video_renderer.get("videoId", "")
            if not video_id:
                continue
            title_runs = video_renderer.get("title", {}).get("runs", [])
            title = title_runs[0].get("text", "") if title_runs else ""
            channel_runs = video_renderer.get("shortBylineText", {}).get("runs", [])
            channel_title = channel_runs[0].get("text", "") if channel_runs else ""
            channel_id = ""
            if channel_runs:
                ch_nav = channel_runs[0].get("navigationEndpoint", {})
                ch_browse = ch_nav.get("browseEndpoint", {})
                if ch_browse.get("browseId", "").startswith("UC"):
                    channel_id = ch_browse["browseId"]
            items.append({
                "id": video_id,
                "snippet": {
                    "title": title,
                    "videoOwnerChannelId": channel_id,
                    "videoOwnerChannelTitle": channel_title,
                    "playlistId": "WL",
                },
                "contentDetails": {"videoId": video_id},
            })
    return items


def scrape_watch_later_videos(max_items: int = 500) -> dict:
    """Fetch native YouTube Watch Later playlist using httpx + saved cookies.

    Uses YouTube's InnerTube API (youtubei.googleapis.com/v1/browse) with
    SAPISID-based authentication from saved cookies.

    Returns dict with 'items' key (list of videos) or error key.
    """
    if not has_cookies():
        log.warning("[HTTPX SCRAPER] No YouTube cookies found. Cannot scrape Watch Later.")
        return {"items": [], "error": "cookies_missing",
                "message": "Export YouTube cookies to continue."}

    try:
        cookies = _load_cookies_raw()
    except (json.JSONDecodeError, OSError) as e:
        log.error("[HTTPX SCRAPER] Failed to read cookies: %s", e)
        return {"items": [], "error": f"cookie_read_failed: {e}"}

    # Build auth
    sapisid_hash = _get_sapisid_hash(cookies)
    cookie_header = _build_cookie_header(cookies)

    if not sapisid_hash:
        log.warning("[HTTPX SCRAPER] No SAPISID cookie found — auth will likely fail")

    base_headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": cookie_header,
    }

    try:
        with httpx.Client(
            timeout=30.0, follow_redirects=True, limits=httpx.Limits(max_connections=2)
        ) as client:
            # Step 1: Fetch the Watch Later page HTML to get API key + client version
            log.info("[HTTPX SCRAPER] Fetching Watch Later page HTML...")
            page_resp = client.get(
                "https://www.youtube.com/playlist?list=WL",
                headers=base_headers,
                timeout=30.0,
            )

            if page_resp.status_code != 200:
                log.error("[HTTPX SCRAPER] Page fetch failed: %d", page_resp.status_code)
                return {"items": [], "error": f"page_fetch_failed: {page_resp.status_code}"}

            html = page_resp.text
            log.info("[HTTPX SCRAPER] Page HTML: %d bytes, status=%d, title=%s", 
                     len(html), page_resp.status_code,
                     (html[html.find('<title>'):html.find('</title>')+8][:100] if '<title>' in html else 'N/A'))

            # Detect sign-in wall
            if "sign in" in html.lower()[:5000] and (
                "data-signin" in html[:5000] or "ytd-button-renderer" in html[:5000]
            ):
                log.warning("[HTTPX SCRAPER] Page shows sign-in wall — cookies may be expired")
                return {"items": [], "error": "auth_required",
                        "message": "YouTube cookies expired or invalid. Re-export from browser."}

            # Extract API key and client version for InnerTube API calls
            api_key = _get_api_key_from_page(html)
            client_version = _get_client_version(html)
            log.info("[HTTPX SCRAPER] API key: %s, client version: %s, sapisid: %s",
                     bool(api_key), client_version, bool(sapisid_hash))
            if not api_key:
                log.warning("[HTTPX SCRAPER] No API key found - InnerTube API calls will fail")
                # Log what keys ARE available
                for key in ['INNERTUBE_API_KEY', 'innertubeApiKey', 'API_KEY']:
                    idx = html.find(key)
                    if idx >= 0:
                        log.warning("[HTTPX SCRAPER] Found '%s' at byte %d: ...%s...", 
                                   key, idx, html[idx:idx+100].replace(chr(10), ' '))

            # Step 2: Build InnerTube auth headers
            api_headers = {
                **base_headers,
                "Authorization": sapisid_hash,
                "X-YouTube-Client-Name": "1",
                "X-YouTube-Client-Version": client_version,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            # Step 3: Try the InnerTube browse endpoint for native WL playlist
            all_items = []
            page_count = 0
            continuation_token = None

            # First attempt: parse ytInitialData from the page HTML (no API call needed)
            yt_data = _extract_yt_initial_data(html)
            if yt_data:
                log.info("[HTTPX SCRAPER] Found ytInitialData in page HTML")
                items = _extract_playlist_items_from_data(yt_data)
                all_items.extend(items)
                log.info("[HTTPX SCRAPER] Extracted %d items from ytInitialData, has_ct=%s", 
                         len(items), bool(_extract_continuation_token(yt_data)))
                continuation_token = _extract_continuation_token(yt_data)
            else:
                log.warning("[HTTPX SCRAPER] No ytInitialData found in page HTML - searching for ytInitialData pattern...")
                # Log a small sample to diagnose
                idx = html.find('ytInitialData')
                if idx >= 0:
                    log.warning("[HTTPX SCRAPER] ytInitialData found at byte %d but regex failed to extract - context: %s...", 
                               idx, html[idx:idx+200].replace(chr(10), ' '))
                else:
                    log.warning("[HTTPX SCRAPER] ytInitialData NOT FOUND in page HTML")

            # If that didn't work, try the InnerTube browse API
            if not all_items and api_key:
                log.info("[HTTPX SCRAPER] No items from HTML, trying InnerTube browse API...")
                browse_payload = {
                    "context": {
                        "client": {
                            "clientName": "WEB",
                            "clientVersion": client_version,
                        }
                    },
                    "browseId": "VLWL",
                }
                browse_url = f"https://www.youtube.com/youtubei/v1/browse?key={api_key}"
                browse_resp = client.post(
                    browse_url, headers=api_headers, json=browse_payload, timeout=30.0
                )

                if browse_resp.status_code == 200:
                    data = browse_resp.json()
                    items = _extract_playlist_items_from_data(data)
                    all_items.extend(items)
                    log.info("[HTTPX SCRAPER] InnerTube API returned %d items", len(items))
                    continuation_token = _extract_continuation_token(data)
                else:
                    log.warning("[HTTPX SCRAPER] InnerTube API returned %d",
                                browse_resp.status_code)
                    # Don't fail yet — try the HTML parsing approach a different way

            # If still nothing, try parsing the HTML page more aggressively
            if not all_items:
                log.info("[HTTPX SCRAPER] Trying HTML content parsing for video data...")
                # Look for video IDs embedded in the page
                vid_matches = re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', html)
                title_matches = re.findall(
                    r'title["\']?\s*:\s*["\']([^"\']+)["\']', html
                )
                unique_vids = list(dict.fromkeys(vid_matches))  # deduplicate preserving order
                for i, vid in enumerate(unique_vids[:max_items]):
                    all_items.append({
                        "id": vid,
                        "snippet": {
                            "title": title_matches[i] if i < len(title_matches) else "",
                            "videoOwnerChannelTitle": "",
                            "playlistId": "WL",
                        },
                        "contentDetails": {"videoId": vid},
                    })
                log.info("[HTTPX SCRAPER] Regex fallback found %d unique video IDs",
                         len(unique_vids))

            # Step 4: Paginate through continuation tokens
            while continuation_token and len(all_items) < max_items:
                page_count += 1
                log.info("[HTTPX SCRAPER] Fetching continuation page %d (token: %s...)",
                         page_count, continuation_token[:30] if continuation_token else "None")

                try:
                    if api_key:
                        data = _fetch_continuation_page(
                            client, api_key, client_version,
                            continuation_token, api_headers
                        )
                    else:
                        # Fallback: use POST to youtubei without API key
                        payload = {
                            "context": {
                                "client": {
                                    "clientName": "WEB",
                                    "clientVersion": client_version,
                                }
                            },
                            "continuation": continuation_token,
                        }
                        resp = client.post(
                            "https://www.youtube.com/youtubei/v1/browse",
                            headers=api_headers, json=payload, timeout=30.0
                        )
                        resp.raise_for_status()
                        data = resp.json()

                    cont_items = _extract_continuation_items(data)
                    all_items.extend(cont_items)
                    log.info("[HTTPX SCRAPER] Continuation page %d returned %d items (total: %d)",
                             page_count, len(cont_items), len(all_items))

                    continuation_token = _extract_continuation_token(data)
                    if not continuation_token:
                        # Check in continuation items too
                        endpoints = data.get("onResponseReceivedEndpoints", [])
                        for ep in endpoints:
                            append = ep.get("appendContinuationItemsAction", {})
                            cont_items_list = append.get("continuationItems", [])
                            for item in reversed(cont_items_list):
                                cont = item.get("continuationItemRenderer", {})
                                if cont:
                                    token = (
                                        cont.get("continuationEndpoint", {})
                                        .get("continuationCommand", {})
                                        .get("token")
                                    )
                                    if token:
                                        continuation_token = token
                                        break

                    # Brief delay to avoid rate limiting
                    if continuation_token:
                        time.sleep(0.5)

                except Exception as e:
                    log.warning("[HTTPX SCRAPER] Continuation page %d failed: %s",
                                page_count, e)
                    break

                if page_count > 20:  # Safety limit
                    log.warning("[HTTPX SCRAPER] Too many continuation pages, stopping")
                    break

            result_items = all_items[:max_items]
            log.info("[HTTPX SCRAPER] Total: %d videos from Watch Later", len(result_items))
            return {"items": result_items}

    except Exception as e:
        log.error("[HTTPX SCRAPER] Scrape failed: %s", e)
        return {"items": [], "error": f"scrape_error: {e}"}
