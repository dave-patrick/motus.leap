"""AI classifier service for motus.leap.
Supports OpenAI, Anthropic (Claude), Groq, and Google AI for video classification.
Also handles training memory — records manual moves and detects channel mapping patterns."""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# Shared httpx.Client for connection reuse (M8)
_shared_client: Optional[httpx.Client] = None


def _get_shared_client() -> httpx.Client:
    """Get or create the shared httpx.Client."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.Client(timeout=30.0)
    return _shared_client


def _classify_sync(provider: str, prompt: str, api_key: str, endpoint: str, model: str = "default") -> tuple:
    """Synchronous classification call (runs in thread)."""
    import httpx
    client = _get_shared_client()
    if provider == "openai":
        resp = client.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 50,
            },
        )
    elif provider == "anthropic":
        resp = client.post(
            endpoint,
            headers={"x-api-key": api_key, "Content-Type": "application/json", "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 50,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    elif provider == "groq":
        resp = client.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 50,
            },
        )
    elif provider == "google":
        resp = client.post(
            endpoint,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 50},
            },
        )
    elif provider == "custom":
        resp = client.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model or "default",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 50,
            },
        )
    else:
        return None, f"Unknown provider: {provider}"
    resp.raise_for_status()
    data = resp.json()
    return data, None

DATA_DIR = Path(__file__).parent.parent / "data"
MEMORY_FILE = DATA_DIR / "ai_memory.json"
MAPPING_THRESHOLD = 3  # Moves from same channel to same playlist triggers mapping suggestion


# ─── Memory / Training Data ───────────────────────────────────────

async def _load_memory() -> list[dict]:
    """Load recorded move examples asynchronously."""
    if not await asyncio.to_thread(MEMORY_FILE.exists):
        return []
    try:
        content = await asyncio.to_thread(MEMORY_FILE.read_text)
        return json.loads(content)
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"Failed to load AI memory: {e}")
        return []


async def _save_memory(memory: list[dict]):
    """Save recorded move examples asynchronously."""
    await asyncio.to_thread(DATA_DIR.mkdir, parents=True, exist_ok=True)
    # Remove entries older than 90 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    memory = [m for m in memory if m.get("timestamp", "") > cutoff]
    try:
        await asyncio.to_thread(MEMORY_FILE.write_text, json.dumps(memory, indent=2))
    except OSError as e:
        log.error(f"Failed to save AI memory: {e}")


async def record_move(video_id: str, title: str, channel_id: str, channel_title: str,
                from_playlist_name: str, from_playlist_id: str,
                to_playlist_name: str, to_playlist_id: str,
                source: str = "manual"):
    """Record a video move for training memory asynchronously.
    
    source: 'manual' (single move from Watch Later modal) or 'sync' (batch sync operation)
    """
    memory = await _load_memory()
    memory.append({
        "video_id": video_id,
        "title": title,
        "channel_id": channel_id,
        "channel_title": channel_title,
        "from_playlist_name": from_playlist_name,
        "from_playlist_id": from_playlist_id,
        "to_playlist_name": to_playlist_name,
        "to_playlist_id": to_playlist_id,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Keep last 1000 moves
    if len(memory) > 1000:
        memory = memory[-1000:]
    await _save_memory(memory)


async def get_channel_mapping_suggestions() -> list[dict]:
    """Analyze training memory and suggest channel -> playlist mappings asynchronously.
    
    If a channel has >= MAPPING_THRESHOLD moves to the same playlist,
    suggest creating a permanent mapping.
    """
    memory = await _load_memory()
    if not memory:
        return []
    
    # Count channel_id -> to_playlist_id occurrences
    from collections import defaultdict
    counts = defaultdict(lambda: defaultdict(int))
    details = {}
    
    for move in memory:
        cid = move.get("channel_id", "") or move.get("channel_title", "")
        to_pid = move.get("to_playlist_id", "")
        to_pname = move.get("to_playlist_name", "")
        if cid and to_pid:
            counts[cid][to_pid] += 1
            details[(cid, to_pid)] = {
                "channel_title": move.get("channel_title", cid),
                "channel_id": move.get("channel_id", ""),
                "playlist_name": to_pname,
                "playlist_id": to_pid,
                "sample_titles": details.get((cid, to_pid), {}).get("sample_titles", []),
            }
            # Collect sample video titles
            samples = details[(cid, to_pid)].get("sample_titles", [])
            if len(samples) < 5:
                samples.append(move.get("title", ""))
            details[(cid, to_pid)]["sample_titles"] = samples
    
    suggestions = []
    for cid, playlist_counts in counts.items():
        for to_pid, count in playlist_counts.items():
            if count >= MAPPING_THRESHOLD:
                d = details.get((cid, to_pid), {})
                suggestions.append({
                    "channel_title": d.get("channel_title", cid),
                    "channel_id": d.get("channel_id", ""),
                    "playlist_name": d.get("playlist_name", to_pid),
                    "playlist_id": to_pid,
                    "move_count": count,
                    "sample_titles": d.get("sample_titles", []),
                })
    # Sort by most moves first, limit to 20
    suggestions.sort(key=lambda x: -x["move_count"])
    return suggestions[:20]


# ─── AI Classification ────────────────────────────────────────────

API_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "google": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
}

DEFAULT_PROMPT = (
    "Classify this YouTube video into one of my playlists based on its title and description. "
    "Return ONLY the playlist name, nothing else. If unsure, return 'UNSURE'."
)


def _build_prompt(prompt_template: str, title: str, channel: str, description: str, playlists: list[dict]) -> str:
    """Build the full prompt for the AI."""
    playlist_names = "\n".join(f"- {p['title']}" for p in playlists)
    return f"""{prompt_template}

MY PLAYLISTS:
{playlist_names}

VIDEO TITLE: {title}
VIDEO CHANNEL: {channel}
VIDEO DESCRIPTION: {description[:500]}

Return ONLY the playlist name or UNSURE."""


async def classify_video(title: str, channel: str, description: str,
                   playlists: list[dict], provider: str, api_key: str,
                   prompt_template: str = DEFAULT_PROMPT,
                   custom_endpoint: str = "", custom_model: str = "") -> tuple[str | None, str | None]:
    """Classify a video into a playlist using the configured AI provider.

    Returns (matched_playlist_name, error_message).
    matched_playlist_name is None if unsure or error.
    """
    if not api_key:
        return None, "No API key configured"
    if not provider:
        return None, "No AI provider configured"
    if not playlists:
        return None, "No playlists available to classify into"

    prompt = _build_prompt(prompt_template, title, channel, description, playlists)

    try:
        endpoint = API_ENDPOINTS.get(provider, "")
        if provider == "google":
            endpoint = f"{endpoint}?key={api_key}"
        elif provider == "custom":
            endpoint = custom_endpoint.rstrip("/") + "/chat/completions"

        data = await asyncio.to_thread(_classify_sync, provider, prompt, api_key, endpoint, custom_model)
        if data is None:
            return None, "Empty response"

        if provider == "openai" or provider == "groq" or provider == "custom":
            text = data["choices"][0]["message"]["content"].strip()
        elif provider == "anthropic":
            text = data["content"][0]["text"].strip()
        elif provider == "google":
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            return None, f"Unknown provider: {provider}"

        return (text if text != "UNSURE" else None), None
    except Exception as e:
        log.error(f"[AI] Classification failed: {e}")
        return None, str(e)
