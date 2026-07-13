"""Configuration manager for motus.leap."""

import json
import logging
from pathlib import Path
from typing import Optional
import asyncio
import aiofiles # For async file operations

from models.config import TubeManagerConfig

log = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration persistence."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the configuration manager.

        Args:
            config_path: Path to config file. Defaults to /app/data/config.json on Render
                        or ./config.json locally.
        """
        self.config_path = config_path or self._get_default_config_path()
        self._config: Optional[TubeManagerConfig] = None
        # Serializes overlapping saves. The background worker updates
        # ``last_scan_time`` and saves while a user /api/settings save may be
        # in flight; without a lock the two write paths can interleave and
        # clobber each other's snapshot on disk.
        self._save_lock = asyncio.Lock()

    def _get_default_config_path(self) -> Path:
        """Get the default config path based on environment."""
        render_path = Path("/app/data/config.json")
        if render_path.exists() or Path("/app/data").exists():
            return render_path
        return Path("config.json")

    async def load(self) -> TubeManagerConfig:
        """Load configuration from file."""
        if self._config is not None:
            return self._config

        try:
            if await asyncio.to_thread(self.config_path.exists):
                async with aiofiles.open(self.config_path, mode='r', encoding='utf-8') as f:
                    content = await f.read()
                data = await asyncio.to_thread(json.loads, content)
                self._config = TubeManagerConfig.from_dict(data)
                # P1 migration: legacy single-provider scalars -> multi-provider
                # list. Only fires when a legacy provider is set but the new
                # ai_providers list is empty, so existing configs don't break
                # (DESIGN_SPEC §7 migration note, Gwen §A.2).
                await self._migrate_legacy_provider(self._config)
                log.info(f"Configuration loaded from {self.config_path}")
            else:
                self._config = TubeManagerConfig()
                log.info("No config file found, using defaults")
        except Exception as e:
            log.error(f"Failed to load config: {e}, using defaults")
            self._config = TubeManagerConfig()

        return self._config

    # ── P1 provider migration (DESIGN_SPEC §7, Gwen §A.2) ──────────────

    async def _migrate_legacy_provider(self, config: "TubeManagerConfig") -> None:
        """Synthesize an ai_providers entry from legacy single-provider scalars.

        If ``ai_provider`` is set but ``ai_providers`` is empty, build a
        ProviderConnection from the legacy scalars (ai_provider, ai_api_key,
        ai_custom_endpoint, ai_custom_model) and set ai_active_provider_id.
        Idempotent: does nothing if ai_providers is already populated.
        """
        from models.config import (
            ProviderConnection,
            PROVIDER_BUILTIN_BASE_URLS,
        )
        from datetime import datetime, timezone
        from pydantic import SecretStr
        import uuid

        if config.ai_providers:
            # Already migrated / multi-provider config; leave untouched.
            if not config.ai_active_provider_id and config.ai_providers:
                # Defensive: if active id missing, pick first enabled provider.
                for p in config.ai_providers:
                    if p.enabled:
                        config.ai_active_provider_id = p.id
                        break
            return

        legacy = (config.ai_provider or "").strip()
        if not legacy:
            return  # nothing to migrate

        # Validate the legacy type against the current enum (defensive).
        if legacy not in ("openai", "anthropic", "groq", "google", "custom"):
            log.warning(
                f"Legacy ai_provider '{legacy}' not in P1 enum; skipping migration."
            )
            return

        key = config.ai_api_key.get_secret_value() if config.ai_api_key else ""

        if legacy == "custom":
            base_url = (config.ai_custom_endpoint or "").rstrip("/")
            # strip any trailing /chat/completions or /v1 leftover from old UI
            for suffix in ("/chat/completions", "/v1"):
                if base_url.endswith(suffix):
                    base_url = base_url[: -len(suffix)]
        else:
            base_url = PROVIDER_BUILTIN_BASE_URLS[legacy]

        selected = [config.ai_custom_model] if legacy == "custom" and config.ai_custom_model else []
        # For builtin types with no discovered/selected models yet, pre-seed the
        # historically-hardcoded default model so classify still works post-cut.
        legacy_default_models = {
            "openai": ["gpt-4o-mini"],
            "anthropic": ["claude-3-haiku-20240307"],
            "groq": ["llama-3.3-70b-versatile"],
            "google": ["gemini-2.0-flash"],
        }
        if legacy in legacy_default_models and not selected:
            selected = list(legacy_default_models[legacy])

        conn = ProviderConnection(
            id=uuid.uuid4().hex,
            name=f"{legacy.capitalize()} (migrated)",
            type=legacy,
            base_url=base_url,
            api_key=SecretStr(key),
            enabled=True,
            selected_models=selected,
            is_builtin=(legacy in PROVIDER_BUILTIN_BASE_URLS),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        config.ai_providers = [conn]
        config.ai_active_provider_id = conn.id
        log.info(f"Migrated legacy ai_provider='{legacy}' -> ai_providers[0].id={conn.id}")

    async def save(self, config: TubeManagerConfig) -> None:
        """Save configuration to file.

        Defensive: merges credential/mapping fields that already exist on disk
        but are empty in the incoming config, so a save can never silently
        clobber OAuth tokens, API/AI keys, or channel mappings (which would
        otherwise wipe YouTube auth or the user's data on any unrelated save).
        """
        async with self._save_lock:
            try:
                await asyncio.to_thread(self.config_path.parent.mkdir, parents=True, exist_ok=True)
                # Merge with any existing on-disk config so fields the caller
                # didn't set (e.g. oauth tokens populated by a parallel flow,
                # or channel_mappings managed elsewhere) are preserved.
                if await asyncio.to_thread(self.config_path.exists):
                    try:
                        existing = json.loads(await asyncio.to_thread(self.config_path.read_text))
                    except Exception:
                        existing = {}
                    if isinstance(existing, dict):
                        incoming = config.to_dict_for_storage()
                        disk_oauth = existing.get("oauth", {}) or {}
                        inc_oauth = incoming.get("oauth", {}) or {}
                        for k in ("access_token", "refresh_token", "client_secret", "client_id", "token_expiry"):
                            if not inc_oauth.get(k) and disk_oauth.get(k) is not None:
                                inc_oauth[k] = disk_oauth[k]
                        incoming["oauth"] = inc_oauth
                        if not incoming.get("youtube_api_key") and existing.get("youtube_api_key"):
                            incoming["youtube_api_key"] = existing["youtube_api_key"]
                        if not incoming.get("ai_api_key") and existing.get("ai_api_key"):
                            incoming["ai_api_key"] = existing["ai_api_key"]
                        # Channel mappings: the incoming config is authoritative.
                        # A prior "lossless" merge re-added every mapping already
                        # on disk even after the caller explicitly cleared it,
                        # so deletions never persisted. We still preserve disk
                        # mappings the incoming config does not enumerate ONLY
                        # when the incoming save is a partial (empty mappings
                        # dict means "clear", not "unknown"). To keep behaviour
                        # predictable: incoming mappings win, but disk mappings
                        # that are genuinely absent from the incoming set AND
                        # were added by a concurrent writer are preserved — UNLESS
                        # the incoming set explicitly removed them. Since we
                        # cannot distinguish a deliberate removal from a stale
                        # save, we make the incoming config authoritative so that
                        # clearing mappings actually persists (per H2 fix).
                        disk_maps = existing.get("channel_mappings") or {}
                        if isinstance(disk_maps, list):
                            from app import _serialize_mappings
                            disk_maps = _serialize_mappings(disk_maps)
                        inc_maps = incoming.get("channel_mappings") or {}
                        if isinstance(inc_maps, list):
                            from app import _serialize_mappings
                            inc_maps = _serialize_mappings(inc_maps)
                        # Authoritative: incoming wins. This makes deletions
                        # persist (set mapping -> clear -> save -> reload == gone).
                        incoming["channel_mappings"] = inc_maps
                        data = incoming
                    else:
                        data = config.to_dict_for_storage()
                else:
                    data = config.to_dict_for_storage()
                async with aiofiles.open(self.config_path, mode='w', encoding='utf-8') as f:
                    await f.write(await asyncio.to_thread(json.dumps, data, indent=2))
                self._config = config
                log.info(f"Configuration saved to {self.config_path}")
            except Exception as e:
                log.error(f"Failed to save config: {e}")
                raise

    @property
    def config(self) -> TubeManagerConfig:
        """Get current configuration. Auto-loads if not yet initialized."""
        if self._config is None:
            # For backward compatibility in tests/edge cases, create default config
            # Note: This should not happen in production as load() is called in lifespan
            self._config = TubeManagerConfig()
            log.warning("Config accessed before load() - using defaults")
        return self._config