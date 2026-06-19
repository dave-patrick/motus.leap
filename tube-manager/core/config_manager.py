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
                log.info(f"Configuration loaded from {self.config_path}")
            else:
                self._config = TubeManagerConfig()
                log.info("No config file found, using defaults")
        except Exception as e:
            log.error(f"Failed to load config: {e}, using defaults")
            self._config = TubeManagerConfig()

        return self._config

    async def save(self, config: TubeManagerConfig) -> None:
        """Save configuration to file."""
        try:
            await asyncio.to_thread(self.config_path.parent.mkdir, parents=True, exist_ok=True)
            data = config.to_dict_for_storage()
            async with aiofiles.open(self.config_path, mode='w', encoding='utf-8') as f:
                await f.write(await asyncio.to_thread(json.dumps, data, indent=2))
            self._config = config
            log.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            log.error(f"Failed to save config: {e}")
            raise

    @property
    async def config(self) -> TubeManagerConfig:
        """Get current configuration, loading if necessary."""
        if self._config is None:
            self._config = await self.load()
        return self._config