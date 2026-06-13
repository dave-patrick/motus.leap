"""Configuration models for Tube Manager."""

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
    sync_watch_later: bool = Field(default=True)
    notify_failures: bool = Field(default=False)
    dark_mode: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    webhook_url: str = Field(default="")

    def to_dict_for_storage(self) -> Dict[str, Any]:
        """Convert to dictionary for safe storage, excluding secrets."""
        data = self.model_dump(exclude_none=True, mode='json')
        data['oauth'] = {
            'client_id': self.oauth.client_id,
            'client_secret': self.oauth.client_secret.get_secret_value() if self.oauth.client_secret else "",
            'access_token': self.oauth.access_token,
            'refresh_token': self.oauth.refresh_token,
            'token_expiry': self.oauth.token_expiry,
        }
        data['youtube_api_key'] = self.youtube_api_key.get_secret_value() if self.youtube_api_key else ""
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