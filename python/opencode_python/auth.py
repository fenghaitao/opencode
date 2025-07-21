"""Authentication management system."""

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Union, Literal

import httpx
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


# GitHub Copilot specific authentication classes and functions
class DeviceCodeResponse(BaseModel):
    """Device code response from GitHub."""
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class AccessTokenResponse(BaseModel):
    """Access token response from GitHub."""
    access_token: Optional[str] = None
    error: Optional[str] = None
    error_description: Optional[str] = None


class CopilotTokenResponse(BaseModel):
    """Copilot token response."""
    token: str
    expires_at: int
    refresh_in: int
    endpoints: Dict[str, str]


class AuthorizeResult(BaseModel):
    """Result from authorize() function."""
    device: str
    user: str
    verification: str
    interval: int
    expiry: int


class PollResult(BaseModel):
    """Result from poll() function."""
    status: Literal["pending", "success", "failed"]
    refresh: Optional[str] = None
    access: Optional[str] = None
    expires: Optional[int] = None


class AccessResult(BaseModel):
    """Result from access() function."""
    refresh: str
    access: str
    expires: int


class GitHubCopilotAuth:
    """GitHub Copilot authentication - Python port of auth.ts."""
    
    CLIENT_ID = "Iv1.b507a08c87ecfe98"
    DEVICE_CODE_URL = "https://github.com/login/device/code"
    ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
    COPILOT_API_KEY_URL = "https://api.github.com/copilot_internal/v2/token"
    
    HEADERS = {
        "User-Agent": "GitHubCopilotChat/0.26.7",
        "Editor-Version": "vscode/1.99.3",
        "Editor-Plugin-Version": "copilot-chat/0.26.7",
        "Copilot-Integration-Id": "vscode-chat",
    }
    
    _log = Log.create({"service": "github-copilot-auth"})
    
    @classmethod
    async def authorize(cls) -> AuthorizeResult:
        """Start GitHub OAuth device flow."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.DEVICE_CODE_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "GitHubCopilotChat/0.26.7",
                },
                json={
                    "client_id": cls.CLIENT_ID,
                    "scope": "read:user",
                }
            )
            response.raise_for_status()
            
            data = DeviceCodeResponse(**response.json())
            
            result = AuthorizeResult(
                device=data.device_code,
                user=data.user_code,
                verification=data.verification_uri,
                interval=data.interval or 5,
                expiry=data.expires_in
            )
            
            cls._log.info("Device authorization started", {
                "user_code": result.user,
                "verification_uri": result.verification,
                "expires_in": result.expiry
            })
            
            return result
    
    @classmethod
    async def poll(cls, device_code: str) -> PollResult:
        """Poll for GitHub OAuth access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.ACCESS_TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "GitHubCopilotChat/0.26.7",
                },
                json={
                    "client_id": cls.CLIENT_ID,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                }
            )
            
            if not response.is_success:
                cls._log.error("Token poll failed", {"status": response.status_code})
                return PollResult(status="failed")
            
            data = AccessTokenResponse(**response.json())
            
            if data.access_token:
                cls._log.info("GitHub OAuth token received", {
                    "token_length": len(data.access_token)
                })
                return PollResult(
                    status="success",
                    refresh=data.access_token,
                    access="",
                    expires=0
                )
            
            if data.error == "authorization_pending":
                return PollResult(status="pending")
            
            if data.error:
                cls._log.error("OAuth error", {
                    "error": data.error,
                    "description": data.error_description
                })
                return PollResult(status="failed")
            
            return PollResult(status="pending")
    
    @classmethod
    async def access(cls, refresh: str) -> Optional[AccessResult]:
        """Exchange GitHub OAuth token for Copilot API token."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cls.COPILOT_API_KEY_URL,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {refresh}",
                    **cls.HEADERS,
                }
            )
            
            if not response.is_success:
                cls._log.error("Failed to get Copilot token", {
                    "status": response.status_code,
                    "response": response.text[:500]
                })
                return None
            
            token_data = CopilotTokenResponse(**response.json())
            
            result = AccessResult(
                refresh=refresh,
                access=token_data.token,
                expires=token_data.expires_at * 1000  # Convert to milliseconds
            )
            
            cls._log.info("Copilot API token obtained", {
                "expires_at": token_data.expires_at,
                "refresh_in": token_data.refresh_in,
                "token_length": len(token_data.token)
            })
            
            return result


class GitHubCopilotAuthManager:
    """High-level GitHub Copilot authentication manager."""
    
    _log = Log.create({"service": "github-copilot-auth-manager"})
    
    @classmethod
    async def start_device_flow(cls) -> AuthorizeResult:
        """Start the device authorization flow."""
        return await GitHubCopilotAuth.authorize()
    
    @classmethod
    async def complete_device_flow(cls, device_code: str) -> bool:
        """Complete the device flow by polling for tokens."""
        result = await GitHubCopilotAuth.poll(device_code)
        
        if result.status == "success" and result.refresh:
            # Store the GitHub OAuth token
            auth_info = OAuthInfo(
                refresh=result.refresh,
                access="",
                expires=0
            )
            await Auth.set("github-copilot", auth_info)
            cls._log.info("GitHub Copilot authentication completed")
            return True
        
        return result.status != "failed"  # Return True for "pending", False for "failed"
    
    @classmethod
    async def get_access_token(cls, force_refresh: bool = False) -> Optional[str]:
        """Get a valid Copilot API access token."""
        # Get stored auth info
        auth_info = await Auth.get("github-copilot")
        if not auth_info or auth_info.type != "oauth":
            cls._log.error("No GitHub Copilot credentials found")
            return None
        
        oauth_info = auth_info
        current_time = int(time.time() * 1000)  # Current time in milliseconds
        
        # Check if we have a valid access token and don't need to refresh
        if (not force_refresh and 
            oauth_info.access and 
            oauth_info.expires > current_time):
            cls._log.debug("Using cached Copilot token", {
                "expires_in": (oauth_info.expires - current_time) // 1000
            })
            return oauth_info.access
        
        # Need to refresh the token
        cls._log.info("Refreshing Copilot API token", {
            "force_refresh": force_refresh,
            "token_expired": oauth_info.expires <= current_time if oauth_info.expires else True
        })
        
        access_result = await GitHubCopilotAuth.access(oauth_info.refresh)
        if not access_result:
            cls._log.error("Failed to refresh Copilot token")
            return None
        
        # Update stored auth info
        updated_auth = OAuthInfo(
            refresh=access_result.refresh,
            access=access_result.access,
            expires=access_result.expires
        )
        await Auth.set("github-copilot", updated_auth)
        
        cls._log.info("Copilot token refreshed successfully", {
            "expires_in": (access_result.expires - current_time) // 1000
        })
        
        return access_result.access
    
    @classmethod
    async def is_authenticated(cls) -> bool:
        """Check if GitHub Copilot is properly authenticated."""
        try:
            token = await cls.get_access_token()
            return token is not None
        except Exception as e:
            cls._log.error("Authentication check failed", {"error": str(e)})
            return False
    
    @classmethod
    async def revoke_authentication(cls) -> None:
        """Remove stored GitHub Copilot credentials."""
        await Auth.remove("github-copilot")
        cls._log.info("GitHub Copilot authentication revoked")