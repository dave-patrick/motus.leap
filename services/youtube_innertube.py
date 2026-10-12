"""Watch Later over YouTube's own web API (InnerTube), without a browser.

Watch Later cannot be read or modified through the YouTube Data API, so this
path used to launch headless Chromium (see core/actions.py). That browser is why
Watch Later sorting needed hundreds of megabytes of RAM, and on a 512 MiB
instance it was killed mid-run. InnerTube is the same private API the YouTube
website itself calls, so the cookie store that already fed Playwright can drive
plain HTTP requests instead: kilobytes of memory instead of a browser process.

Everything on the public Data API keeps using services/youtube_client.py.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from typing import Any, Iterator, Optional

import httpx

log = logging.getLogger(__name__)

YOUTUBE_ORIGIN = "https://www.youtube.com"
BROWSE_ENDPOINT = f"{YOUTUBE_ORIGIN}/youtubei/v1/browse"
EDIT_PLAYLIST_ENDPOINT = f"{YOUTUBE_ORIGIN}/youtubei/v1/browse/edit_playlist"

# 'VL' + the playlist id. The feed-style 'FEwatch_later' id is rejected with 400.
WATCH_LATER_BROWSE_ID = "VLWL"
WATCH_LATER_PLAYLIST_ID = "WL"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
_COOKIE_DOMAINS = ("youtube.com", "google.com")
_CONFIG_TTL_SECONDS = 6 * 60 * 60
_MAX_CONTINUATION_PAGES = 40
_REQUEST_TIMEOUT = 60.0

_config_cache: dict[str, Any] = {"api_key": "", "client_version": "", "fetched_at": 0.0}


class InnerTubeError(RuntimeError):
    """Watch Later could not be handled over InnerTube; a browser may still work."""


class WatchLaterSessionError(InnerTubeError):
    """YouTube answered as a signed-out visitor.

    The stored cookies are missing or stale. This is deliberately a distinct type
    so callers never answer it by launching a browser: a browser without a
    signed-in session fails the same way, only after paying hundreds of megabytes
    to prove it.
    """


def _new_client() -> httpx.Client:
    """HTTP client for InnerTube calls. Patched in tests."""
    return httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True)


def reset_cache() -> None:
    """Forget the cached InnerTube client config (used by tests)."""
    _config_cache.update({"api_key": "", "client_version": "", "fetched_at": 0.0})


def _netscape_cookies(text: str) -> list[dict[str, str]]:
    """Parse a Netscape cookies.txt export into cookie dicts."""
    cookies = []
    for line in text.splitlines():
        line = line.strip()
        if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
            continue
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        cookies.append({"name": parts[5], "value": "\t".join(parts[6:]), "domain": parts[0]})
    return cookies


def _read_cookie_file(path: str) -> list[dict[str, str]]:
    """Read the cookie store, accepting either the JSON store or a Netscape file."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    try:
        raw = json.loads(text)
    except ValueError:
        return _netscape_cookies(text)
    if isinstance(raw, dict):
        raw = raw.get("cookies") or []
    return [cookie for cookie in raw if isinstance(cookie, dict)]


def _load_cookie_jar() -> dict[str, str]:
    """Read the stored Playwright cookie file into a name -> value mapping."""
    from core.actions import get_youtube_cookies_path

    path = get_youtube_cookies_path()
    if not path or not os.path.exists(path):
        raise WatchLaterSessionError(
            "No YouTube cookies are stored. Export them from a signed-in youtube.com "
            "tab and import them under Settings > Browser Session."
        )
    try:
        raw = _read_cookie_file(path)
    except OSError as exc:
        raise WatchLaterSessionError(
            f"Could not read the stored YouTube cookies: {exc}"
        ) from exc

    jar: dict[str, str] = {}
    for cookie in raw:
        if not isinstance(cookie, dict):
            continue
        name, value = cookie.get("name"), cookie.get("value")
        if not name or value is None:
            continue
        domain = str(cookie.get("domain") or "").lstrip(".").casefold()
        if not any(domain == suffix or domain.endswith("." + suffix) for suffix in _COOKIE_DOMAINS):
            continue
        jar[str(name)] = str(value)

    if not jar:
        raise WatchLaterSessionError(
            "The stored cookie file has no YouTube or Google cookies in it. Export "
            "cookies from youtube.com while signed in and import them again."
        )
    return jar


def is_configured() -> bool:
    """True when a usable cookie store is on disk."""
    try:
        _load_cookie_jar()
        return True
    except WatchLaterSessionError:
        return False


def _sapisid(jar: dict[str, str]) -> str:
    for name in ("SAPISID", "__Secure-3PAPISID", "__Secure-1PAPISID"):
        if jar.get(name):
            return jar[name]
    raise WatchLaterSessionError(
        "The stored YouTube cookies have no SAPISID value, so requests cannot be "
        "authenticated. Export cookies from youtube.com while signed in."
    )


def _request_headers(jar: dict[str, str]) -> dict[str, str]:
    """Cookies plus the SAPISIDHASH signature YouTube requires for web writes."""
    timestamp = int(time.time())
    digest = hashlib.sha1(f"{timestamp} {_sapisid(jar)} {YOUTUBE_ORIGIN}".encode()).hexdigest()
    return {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": "; ".join(f"{name}={value}" for name, value in jar.items()),
        "Origin": YOUTUBE_ORIGIN,
        "X-Origin": YOUTUBE_ORIGIN,
        "Authorization": f"SAPISIDHASH {timestamp}_{digest}",
        "Content-Type": "application/json",
    }


def _require_match(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text)
    if not match:
        raise InnerTubeError(f"Could not read {label} from youtube.com.")
    return match.group(1)


def _fetch_client_config(http: httpx.Client, jar: dict[str, str]) -> dict[str, Any]:
    response = http.get(f"{YOUTUBE_ORIGIN}/", headers=_request_headers(jar))
    response.raise_for_status()
    html = response.text
    return {
        "api_key": _require_match(r'"INNERTUBE_API_KEY":"([^"]+)"', html, "the InnerTube API key"),
        "client_version": _require_match(
            r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html, "the InnerTube client version"
        ),
        "fetched_at": time.time(),
    }


def _client_config(http: httpx.Client, jar: dict[str, str], force: bool = False) -> dict[str, Any]:
    fresh_enough = (time.time() - _config_cache["fetched_at"]) < _CONFIG_TTL_SECONDS
    if not force and _config_cache["api_key"] and fresh_enough:
        return _config_cache
    _config_cache.update(_fetch_client_config(http, jar))
    return _config_cache


def _context(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "client": {
            "clientName": "WEB",
            "clientVersion": config["client_version"],
            "hl": "en",
            "gl": "US",
        }
    }


def _walk(node: Any) -> Iterator[dict[str, Any]]:
    """Yield every dict in a response, so renderer lookups survive layout changes."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _text(node: Any) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("content"):
        return str(node["content"])
    if node.get("simpleText"):
        return str(node["simpleText"])
    runs = node.get("runs")
    if isinstance(runs, list):
        return "".join(str(run.get("text", "")) for run in runs if isinstance(run, dict))
    return ""


def _logged_in(payload: dict[str, Any]) -> Optional[bool]:
    """Read YouTube's own logged_in flag, or None when it is absent."""
    params = (payload.get("responseContext") or {}).get("serviceTrackingParams") or []
    for service in params:
        for pair in service.get("params") or []:
            if pair.get("key") == "logged_in":
                return pair.get("value") == "1"
    return None


def _alert_text(payload: dict[str, Any]) -> str:
    messages = []
    for alert in payload.get("alerts") or []:
        text = (alert.get("alertRenderer") or {}).get("text")
        rendered = _text(text)
        if rendered:
            messages.append(rendered)
    return " ".join(messages).strip()


def _signed_out_message(payload: dict[str, Any]) -> str:
    detail = _alert_text(payload)
    suffix = f" YouTube said: {detail}" if detail else ""
    return (
        "The stored YouTube cookies are no longer signed in. Export fresh cookies "
        "from a signed-in youtube.com tab and import them under Settings > Browser "
        f"Session.{suffix}"
    )


def _raise_if_signed_out(payload: dict[str, Any]) -> None:
    if _logged_in(payload) is False:
        raise WatchLaterSessionError(_signed_out_message(payload))


def _post(
    http: httpx.Client,
    config: dict[str, Any],
    endpoint: str,
    body: dict[str, Any],
    jar: dict[str, str],
) -> dict[str, Any]:
    url = f"{endpoint}?prettyPrint=false&key={config['api_key']}"
    response = http.post(url, headers=_request_headers(jar), json=body)
    if response.status_code == 400:
        raise InnerTubeError("YouTube rejected the request (HTTP 400).")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise InnerTubeError("YouTube returned an unexpected response body.")
    return payload


def _call(
    http: httpx.Client,
    jar: dict[str, str],
    endpoint: str,
    build_body,
) -> dict[str, Any]:
    """POST, refreshing the client config once if YouTube rejects it."""
    config = _client_config(http, jar)
    try:
        return _post(http, config, endpoint, build_body(config), jar)
    except InnerTubeError as exc:
        log.warning(f"InnerTube call to {endpoint} failed ({exc}); refreshing client config.")
    config = _client_config(http, jar, force=True)
    return _post(http, config, endpoint, build_body(config), jar)


def _video(video_id: str, title: str, channel: str) -> dict[str, Any]:
    return {
        "video_id": video_id,
        # Kept alongside video_id because older callers read 'id'.
        "id": video_id,
        "title": title or video_id,
        "channel": channel or "Unknown",
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "published": "",
    }


def _collect_videos(payload: dict[str, Any], videos: dict[str, dict[str, Any]]) -> None:
    for node in _walk(payload):
        renderer = node.get("playlistVideoRenderer")
        if isinstance(renderer, dict):
            video_id = renderer.get("videoId")
            if isinstance(video_id, str) and VIDEO_ID_PATTERN.match(video_id):
                videos.setdefault(
                    video_id,
                    _video(video_id, _text(renderer.get("title")), _text(renderer.get("shortBylineText"))),
                )
            continue
        lockup = node.get("lockupViewModel")
        if isinstance(lockup, dict):
            video_id = lockup.get("contentId")
            # Playlists and channels also use lockups; only 11-character ids are videos.
            if isinstance(video_id, str) and VIDEO_ID_PATTERN.match(video_id):
                metadata = (lockup.get("metadata") or {}).get("lockupMetadataViewModel") or {}
                videos.setdefault(video_id, _video(video_id, _text(metadata.get("title")), ""))


def _continuation_token(payload: dict[str, Any]) -> str:
    """Return the next-page token, wherever YouTube nested it.

    The token used to sit at ``continuationEndpoint.continuationCommand``, but
    Watch Later now nests it under
    ``continuationEndpoint.commandExecutorCommand.commands[]``. A page can also
    carry a token-less "Reload for updates" popup renderer, so we scan every
    continuation renderer's subtree and take the first real token.
    """
    for node in _walk(payload):
        renderer = node.get("continuationItemRenderer")
        if not isinstance(renderer, dict):
            continue
        for child in _walk(renderer):
            command = child.get("continuationCommand")
            if isinstance(command, dict) and command.get("token"):
                return str(command["token"])
    return ""


def list_watch_later(client: Optional[httpx.Client] = None) -> list[dict[str, Any]]:
    """Return every video in Watch Later, newest first as YouTube orders them.

    Raises WatchLaterSessionError when the stored cookies are not signed in, and
    InnerTubeError for anything else. An empty list means Watch Later is empty.
    """
    jar = _load_cookie_jar()
    videos: dict[str, dict[str, Any]] = {}
    http = client or _new_client()
    try:
        payload = _call(
            http, jar, BROWSE_ENDPOINT, lambda config: {"context": _context(config), "browseId": WATCH_LATER_BROWSE_ID}
        )
        _raise_if_signed_out(payload)
        for _ in range(_MAX_CONTINUATION_PAGES):
            _collect_videos(payload, videos)
            token = _continuation_token(payload)
            if not token:
                break
            payload = _call(http, jar, BROWSE_ENDPOINT, lambda config: {"context": _context(config), "continuation": token})
            _raise_if_signed_out(payload)
        else:
            raise InnerTubeError("Watch Later did not finish loading; too many continuation pages.")
    finally:
        if client is None:
            http.close()
    return list(videos.values())


def remove_from_watch_later(video_id: str, client: Optional[httpx.Client] = None) -> bool:
    """Remove one video from Watch Later. True only when YouTube confirms it."""
    if not isinstance(video_id, str) or not VIDEO_ID_PATTERN.match(video_id):
        raise InnerTubeError(f"Not a YouTube video id: {video_id!r}")

    body_extra = {
        "playlistId": WATCH_LATER_PLAYLIST_ID,
        "actions": [{"action": "ACTION_REMOVE_VIDEO_BY_VIDEO_ID", "removedVideoId": video_id}],
    }
    jar = _load_cookie_jar()
    http = client or _new_client()
    try:
        payload = _call(http, jar, EDIT_PLAYLIST_ENDPOINT, lambda config: {"context": _context(config), **body_extra})
    finally:
        if client is None:
            http.close()

    status = payload.get("status")
    if status == "STATUS_SUCCEEDED":
        return True
    _raise_if_signed_out(payload)
    detail = _alert_text(payload)
    raise InnerTubeError(
        f"YouTube did not confirm the removal ({status or 'no status'})"
        + (f": {detail}" if detail else ".")
    )