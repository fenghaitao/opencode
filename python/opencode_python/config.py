"""Configuration management."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .global_config import Path as GlobalPath
from .util.log import Log, LogLevel


class ConfigModel(BaseModel):
    """Configuration model."""
    
    log_level: Optional[LogLevel] = None
    autoshare: bool = False
    default_provider: Optional[str] = "github-copilot"
    default_model: Optional[str] = "gpt-4.1"
    providers: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    tools: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    modes: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class Config:
    """Configuration manager."""
    
    _log = Log.create({"service": "config"})
    _config_path = GlobalPath.config / "config.json"
    _cached_config: Optional[ConfigModel] = None
    
    @classmethod
    async def get(cls) -> ConfigModel:
        """Get current configuration."""
        if cls._cached_config is not None:
            return cls._cached_config
        
        try:
            if cls._config_path.exists():
                with open(cls._config_path, 'r') as f:
                    data = json.load(f)
                cls._cached_config = ConfigModel(**data)
            else:
                cls._cached_config = ConfigModel()
                await cls.save(cls._cached_config)
        except Exception as e:
            cls._log.error("Failed to load config", {"error": str(e)})
            cls._cached_config = ConfigModel()
        
        return cls._cached_config
    
    @classmethod
    async def save(cls, config: ConfigModel) -> None:
        """Save configuration."""
        try:
            cls._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cls._config_path, 'w') as f:
                json.dump(config.model_dump(exclude_none=True), f, indent=2)
            cls._cached_config = config
            cls._log.info("Configuration saved")
        except Exception as e:
            cls._log.error("Failed to save config", {"error": str(e)})
            raise
    
    @classmethod
    async def update(cls, updates: Dict[str, Any]) -> ConfigModel:
        """Update configuration with new values."""
        config = await cls.get()
        
        # Update fields
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        await cls.save(config)
        return config
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached configuration."""
        cls._cached_config = None