"""Configuration models for motus.leap."""

from pydantic import BaseModel, Field, SecretStr
from typing import Optional, Dict, Any, List

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
    last_scan_time: Optional[str] = Field(default=None)
    # Resolved channel metadata (name/avatar) keyed by channel ID. Populated by
    # the mappings UI's name-enrichment pass and persisted so names survive a
    # reload without re-hitting the YouTube API every time.
    channel_metadata: Dict[str, Dict[str, str]] = Field(default_factory=dict)

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
        data['oauth'] = {
            'client_id': self.oauth.client_id,
            'client_secret': _secret(self.oauth.client_secret) if self.oauth.client_secret else '',
            'access_token': _secret(self.oauth.access_token) if self.oauth.access_token else None,
            'refresh_token': _secret(self.oauth.refresh_token) if self.oauth.refresh_token else None,
            'token_expiry': self.oauth.token_expiry,
        }
        data['youtube_api_key'] = _secret(self.youtube_api_key) if self.youtube_api_key else ''
        data['ai_api_key'] = _secret(self.ai_api_key) if self.ai_api_key else ''
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