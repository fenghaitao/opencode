"""Authentication management system."""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Union

from pydantic import BaseModel

from .global_config import Path as GlobalPath
from .util.log import Log


class OAuthInfo(BaseModel):
    """OAuth authentication information."""
    type: str = "oauth"
    refresh: str
    access: str
    expires: int


class ApiKeyInfo(BaseModel):
    """API key authentication information."""
    type: str = "api"
    key: str


AuthInfo = Union[OAuthInfo, ApiKeyInfo]


class Auth:
    """Authentication management."""
    
    _log = Log.create({"service": "auth"})
    _auth_file = GlobalPath.data / "auth.json"
    
    @classmethod
    async def get(cls, provider_id: str) -> Optional[AuthInfo]:
        """Get authentication info for a provider."""
        try:
            if not cls._auth_file.exists():
                return None
            
            with open(cls._auth_file, 'r') as f:
                data = json.load(f)
            
            provider_data = data.get(provider_id)
            if not provider_data:
                return None
            
            if provider_data.get("type") == "oauth":
                return OAuthInfo(**provider_data)
            else:
                return ApiKeyInfo(**provider_data)
        
        except Exception as e:
            cls._log.error("Failed to get auth info", {"provider": provider_id, "error": str(e)})
            return None
    
    @classmethod
    async def all(cls) -> Dict[str, AuthInfo]:
        """Get all authentication info."""
        try:
            if not cls._auth_file.exists():
                return {}
            
            with open(cls._auth_file, 'r') as f:
                data = json.load(f)
            
            result = {}
            for provider_id, provider_data in data.items():
                if provider_data.get("type") == "oauth":
                    result[provider_id] = OAuthInfo(**provider_data)
                else:
                    result[provider_id] = ApiKeyInfo(**provider_data)
            
            return result
        
        except Exception as e:
            cls._log.error("Failed to get all auth info", {"error": str(e)})
            return {}
    
    @classmethod
    async def set(cls, provider_id: str, auth_info: AuthInfo) -> None:
        """Set authentication info for a provider."""
        try:
            # Load existing data
            data = {}
            if cls._auth_file.exists():
                with open(cls._auth_file, 'r') as f:
                    data = json.load(f)
            
            # Update with new info
            data[provider_id] = auth_info.model_dump()
            
            # Ensure directory exists
            cls._auth_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write back
            with open(cls._auth_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Set secure permissions (readable only by owner)
            os.chmod(cls._auth_file, 0o600)
            
            cls._log.info("Saved auth info", {"provider": provider_id, "type": auth_info.type})
        
        except Exception as e:
            cls._log.error("Failed to save auth info", {"provider": provider_id, "error": str(e)})
            raise
    
    @classmethod
    async def remove(cls, provider_id: str) -> None:
        """Remove authentication info for a provider."""
        try:
            if not cls._auth_file.exists():
                return
            
            with open(cls._auth_file, 'r') as f:
                data = json.load(f)
            
            if provider_id in data:
                del data[provider_id]
                
                with open(cls._auth_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                os.chmod(cls._auth_file, 0o600)
                cls._log.info("Removed auth info", {"provider": provider_id})
        
        except Exception as e:
            cls._log.error("Failed to remove auth info", {"provider": provider_id, "error": str(e)})
            raise
    
    @classmethod
    def get_auth_file_path(cls) -> str:
        """Get the path to the auth file for display."""
        home = Path.home()
        try:
            relative_path = cls._auth_file.relative_to(home)
            return f"~/{relative_path}"
        except ValueError:
            return str(cls._auth_file)