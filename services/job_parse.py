"""Natural-language -> cron+task parsing for scheduled jobs (P3).

Reuses the active AI provider exactly like P2's chat (ai_chat.run_chat's
provider resolution + fallback). The model is asked for a STRICT JSON object:

    {"cron": "<5-field>", "task": {"type": "<action>", "payload": {...}},
     "name": "<short label>", "explain": "<one line>"}

The result is validated against the same strict schema the POST /api/ai/jobs
endpoint uses (cron parses, task.type in ALLOWED_JOB_ACTIONS, task has no
unknown keys) before it is returned. If the model returns anything invalid we
raise a clear error rather than silently forwarding it (M4 — never pass raw
model text into a schedule).
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple

from models.config import TubeManagerConfig
from models.scheduled_job import ALLOWED_JOB_ACTIONS
from services import cron_util

log = logging.getLogger(__name__)

_SYSTEM = (
    "You schedule maintenance jobs for a YouTube playlist manager. "
    "Given a natural-language request, output ONLY a JSON object (no prose, "
    "no markdown fences) with these exact keys:\n"
    "  cron: a 5-field cron expression (minute hour day-of-month month day-of-week). "
    "Use '*' and numeric values only (no names). Example: '0 3 * * *' = daily at 3am.\n"
    "  name: a short human label (<=40 chars).\n"
    "  task: an object {type, payload}. type must be one of: "
    f"{sorted(ALLOWED_JOB_ACTIONS)}. "
    "payload is an object; for scan_duplicates/scan_misplaced use "
    "{\"playlist_id\": \"<id or empty string for whole library>\"}.\n"
    "  explain: one short sentence describing the schedule.\n"
    "Destructive types (move_video, delete_video, remove_duplicates) MUST only be "
    "used when the user explicitly asks to remove/move/delete. Otherwise prefer "
    "scan_duplicates / scan_misplaced (read-only)."
)


def _validate(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the model's parsed object; raise ValueError on any problem."""
    if not isinstance(parsed, dict):
        raise ValueError("provider did not return a JSON object")

    cron = parsed.get("cron")
    if not isinstance(cron, str) or not cron_util.cron_valid(cron):
        raise ValueError(f"invalid or unparseable cron: {cron!r}")

    task = parsed.get("task")
    if not isinstance(task, dict):
        raise ValueError("task must be an object")
    ttype = task.get("type")
    if ttype not in ALLOWED_JOB_ACTIONS:
        raise ValueError(f"unknown task type '{ttype}'")
    payload = task.get("payload", {})
    if not isinstance(payload, dict):
        raise ValueError("task.payload must be an object")

    name = parsed.get("name") or (parsed.get("explain") or "Untitled job")[:40]
    return {
        "cron": cron,
        "name": str(name)[:80],
        "task": {"type": ttype, "payload": payload},
        "explain": parsed.get("explain", ""),
    }


def parse_schedule_nl(
    text: str,
    config: TubeManagerConfig,
    simulate_provider: Any = None,
) -> Dict[str, Any]:
    """Parse NL into a validated {cron, name, task, explain}.

    ``simulate_provider`` is the same test seam as ai_chat.run_chat: a callable
    ``(messages, system) -> response_dict``. When None, the real active provider
    is used with P1 fallback (Decision 4).
    """
    messages = [{"role": "system", "content": _SYSTEM},
                {"role": "user", "content": text}]

    if simulate_provider is not None:
        resp = simulate_provider(messages, _SYSTEM)
    else:
        resp = _call_provider(config, messages)

    content = _extract_content(resp)
    # The model is told to return bare JSON; extract content between first '{' and last '}'
    # to tolerate markdown fences and conversational filler robustly.
    content = content.strip()
    start = content.find('{')
    end = content.rfind('}')
    if start != -1 and end != -1:
        content = content[start:end+1]
    elif content.startswith("```"):
        content = content.strip("`")
        content = content.split("\n", 1)[-1] if "\n" in content else content
    try:
        parsed = json.loads(content)
    except Exception:
        raise ValueError("provider did not return valid JSON")
    return _validate(parsed)


def _extract_content(resp: Optional[Dict[str, Any]]) -> str:
    if not resp:
        raise ValueError("no provider response")
    try:
        msg = resp["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("unexpected provider response shape")
    content = msg.get("content") or ""
    # Some providers emit tool_calls instead of content for structured asks;
    # fall back to the first tool_call's arguments if present.
    if not content and msg.get("tool_calls"):
        try:
            content = msg["tool_calls"][0]["function"]["arguments"]
        except Exception:
            pass
    return content


def _call_provider(config: TubeManagerConfig, messages: list) -> Dict[str, Any]:
    """Resolve the active provider with P1 fallback (Decision 4)."""
    from services.ai_chat import (_iter_enabled_providers,
                                   _provider_default_model,
                                   _chat_completion, _redact)
    last_err = None
    for conn in _iter_enabled_providers(config):
        model = _provider_default_model(conn)
        if not model:
            continue
        try:
            return _chat_completion(conn, model, messages, tools=[])
        except Exception as e:
            last_err = str(e)
            log.warning("[JOBS-PARSE] provider %s failed: %s", conn.name, _redact(str(e)))
            continue
    if last_err:
        raise RuntimeError(_redact(last_err))
    raise RuntimeError("No AI providers configured — cannot parse schedule")
