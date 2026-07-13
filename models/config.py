"""Configuration models for motus.leap."""

import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field, SecretStr
from typing import Optional, Dict, Any, List

# Provider type enum for the P1 multi-provider model. openai/groq/custom speak
# the OpenAI-compatible /v1/models surface (live probe); anthropic/google do NOT
# and are served a curated catalog / manual-entry (see DESIGN_SPEC §7, Gwen §A.2).
PROVIDER_TYPES = ["openai", "anthropic", "groq", "google", "custom"]

# Builtin base URLs for known providers (no /v1 suffix; code appends as needed).
PROVIDER_BUILTIN_BASE_URLS = {
    "openai": "https://api.openai.com",
    "anthropic": "https://api.anthropic.com",
    "groq": "https://api.groq.com",
    "google": "https://generativelanguage.googleapis.com",
}


class ProviderConnection(BaseModel):
    """A named AI provider connection (P1 multi-provider model).

    Replaces the legacy single-provider scalar fields. Each connection carries
    its own base URL + key + selected/discovered models. ``api_key`` is a
    SecretStr so it is never serialized into API responses by default.
    """
    id: str                                  # uuid hex — stable reference
    name: str                                # user-given label, e.g. "My Groq"
    type: str                                # one of PROVIDER_TYPES
    base_url: str = ""                       # e.g. https://api.groq.com (no trailing /v1)
    api_key: SecretStr = Field(default=SecretStr(""))
    enabled: bool = True
    selected_models: List[str] = []          # ids chosen by user after discovery
    discovered_models: List[str] = []        # cache of last GET /v1/models result
    discovered_at: Optional[str] = None
    is_builtin: bool = False                 # True for the 4 default providers
    created_at: str = ""

    def redacted(self) -> Dict[str, Any]:
        """Return a dict safe to expose to the client (no api_key)."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "base_url": self.base_url,
            "enabled": self.enabled,
            "selected_models": list(self.selected_models),
            "discovered_models": list(self.discovered_models),
            "discovered_at": self.discovered_at,
            "is_builtin": self.is_builtin,
            "created_at": self.created_at,
        }


class AIRule(BaseModel):
    """An AI classification rule (P2).

    Maps a natural-language rule ("all aviation videos → Aviation playlist")
    to a target playlist. Persisted in ``TubeManagerConfig.ai_rules`` which is
    the single source of truth — the chat agent's ``apply_rules`` tool only
    READS these (P1-7 / DESIGN_SPEC §7); it never mutates the store.

    ``target_playlist`` is the canonical key (playlist id) used for the
    one-rule-per-target uniqueness constraint (Decision 2). ``playlist_name``
    is a denormalized display value refreshed from the user's library.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    description: str = ""                       # NL rule text
    target_playlist: str = ""                  # playlist id (uniqueness key)
    playlist_name: str = ""                    # denormalized display name
    model: str = ""                            # model id this rule was built with
    enabled: bool = True
    is_global: bool = False
    priority: int = 0
    matched_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIRule":
        return cls(**data)

    def redacted(self) -> Dict[str, Any]:
        """No secrets possible, but keep a stable client shape."""
        return self.model_dump()


class YouTubeOAuthConfig(BaseModel):
    """YouTube OAuth configuration."""
    client_id: str = Field(default="")
    client_secret: SecretStr = Field(default="")
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[int] = None

class TubeManagerConfig(BaseModel):
    """Main application configuration."""
    youtube_api_key: SecretStr = Field(default="")
    oauth: YouTubeOAuthConfig = Field(default_factory=YouTubeOAuthConfig)
    channel_mappings: Dict[str, str] = Field(default_factory=dict)
    rules: Optional[str] = None
    default_privacy: str = Field(default="private")
    scan_interval: str = Field(default="hourly")
    max_concurrent: int = Field(default=3)
    auto_sort: bool = Field(default=True)
    notify_failures: bool = Field(default=False)
    dark_mode: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    ai_provider: str = Field(default="")
    ai_api_key: SecretStr = Field(default="")
    ai_mode: str = Field(default="channel")
    ai_classification_prompt: str = Field(default="Classify this YouTube video into one of my playlists based on its title and description. Return ONLY the playlist name, nothing else. If unsure, return 'UNSURE'.")
    ai_custom_endpoint: str = Field(default="")
    ai_custom_model: str = Field(default="")
    ai_auto_apply_mappings: bool = Field(default=False)
    # ── P1 multi-provider model (replaces/extends the legacy single-provider scalars above) ──
    ai_providers: List[ProviderConnection] = Field(default_factory=list)
    ai_active_provider_id: Optional[str] = None
    last_scan_time: Optional[str] = Field(default=None)
    # Resolved channel metadata (name/avatar) keyed by channel ID. Populated by
    # the mappings UI's name-enrichment pass and persisted so names survive a
    # reload without re-hitting the YouTube API every time.
    channel_metadata: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    # Whether open self-registration is permitted. Disabled by default so the
    # app does not expose a public sign-up; enable explicitly via config.
    allow_self_registration: bool = Field(default=False)
    # Explicit list of additional allowed CORS/Origin values (CSRF guard).
    # M2: only declared origins are trusted; blanket *.onrender.com is removed.
    allowed_origins: List[str] = Field(default_factory=list)
    # ── P2 AI Rules + AI Chat ──
    ai_rules: List[AIRule] = Field(default_factory=list)
    # Per-user (by identity) chat request ceiling per minute (M8). 0 = unlimited.
    ai_chat_rate_limit_per_min: int = Field(default=20)

    def to_dict_for_storage(self) -> Dict[str, Any]:
        """Convert to dictionary for storage.

        NOTE: OAuth tokens ARE persisted here (the on-disk config at
        /app/data/config.json is the app's private credential store and the
        live app needs them to stay authenticated across reloads/saves).
        They are NOT exposed via any API response — endpoints redact them
        before sending to the client — so persisting them is safe and
        required to prevent every config save from silently disconnecting
        YouTube.
        """
        def _secret(val):
            """Safely extract secret value from SecretStr or plain string."""
            if hasattr(val, 'get_secret_value'):
                return val.get_secret_value()
            return str(val) if val else ""

        data = self.model_dump(exclude_none=True)
        # Serialize the P1 multi-provider list. ProviderConnection.api_key is a
        # SecretStr; expand it to its raw secret string so json.dumps (used by
        # ConfigManager.save via to_dict_for_storage) works, and so the value
        # round-trips through disk -> from_dict (which re-wraps as SecretStr).
        if self.ai_providers:
            # mode="json" renders SecretStr.api_key to its raw secret string so
            # json.dumps (ConfigManager.save) succeeds and round-trips on load.
            data['ai_providers'] = [
                p.model_dump(mode="json") for p in self.ai_providers
            ]
        data['oauth'] = {
            'client_id': self.oauth.client_id,
            'client_secret': _secret(self.oauth.client_secret) if self.oauth.client_secret else '',
            'access_token': _secret(self.oauth.access_token) if self.oauth.access_token else None,
            'refresh_token': _secret(self.oauth.refresh_token) if self.oauth.refresh_token else None,
            'token_expiry': self.oauth.token_expiry,
        }
        data['youtube_api_key'] = _secret(self.youtube_api_key) if self.youtube_api_key else ''
        data['ai_api_key'] = _secret(self.ai_api_key) if self.ai_api_key else ''
        # P2: serialize ai_rules (no secrets; plain models).
        data['ai_rules'] = [r.model_dump() for r in self.ai_rules]
        data['ai_chat_rate_limit_per_min'] = self.ai_chat_rate_limit_per_min
        return data
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TubeManagerConfig':
        """Create from dictionary, handling nested structures."""
        if not data:
            return cls()
        
        oauth_data = data.pop('oauth', {})
        oauth_config = YouTubeOAuthConfig(
            client_id=oauth_data.get('client_id', ''),
            client_secret=oauth_data.get('client_secret', ''),
            access_token=oauth_data.get('access_token'),
            refresh_token=oauth_data.get('refresh_token'),
            token_expiry=oauth_data.get('token_expiry')
        )
        
        data['youtube_api_key'] = data.get('youtube_api_key', '')
        data['oauth'] = oauth_config
        
        return cls(**data)