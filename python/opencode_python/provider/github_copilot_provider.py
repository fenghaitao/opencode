"""GitHub Copilot provider implementation."""

import json
import os
import time
from typing import Dict, List, Optional

import httpx
from pydantic import BaseModel

from ..auth import Auth, OAuthInfo, GitHubCopilotAuthManager
from ..util.error import NamedError
from ..util.log import Log
from .provider import Provider, ProviderInfo, ModelInfo, ChatRequest, ChatResponse, ChatMessage


class GitHubCopilotProvider(Provider):
    """GitHub Copilot provider implementation."""
    
    def __init__(self):
        super().__init__("github-copilot")
        self._auth = GitHubCopilotAuthManager()
        self._log = Log.create({"service": "github-copilot"})
    
    async def get_info(self) -> ProviderInfo:
        """Get provider information."""
        return ProviderInfo(
            id=self.id,
            name="GitHub Copilot",
            description="GitHub Copilot AI assistant",
            requires_auth=True,
            auth_url="https://github.com/settings/copilot",
            models=[
                # OpenAI models
                ModelInfo(
                    id="gpt-4o",
                    name="GPT-4o (Copilot)",
                    description="GitHub Copilot's GPT-4o model",
                    context_length=128000,
                    supports_tools=True,
                    cost_per_input_token=0.0,  # Free with Copilot subscription
                    cost_per_output_token=0.0,
                ),
                ModelInfo(
                    id="gpt-4o-mini",
                    name="GPT-4o Mini (Copilot)",
                    description="GitHub Copilot's GPT-4o Mini model",
                    context_length=128000,
                    supports_tools=True,
                    cost_per_input_token=0.0,
                    cost_per_output_token=0.0,
                ),
                ModelInfo(
                    id="o1-preview",
                    name="o1 Preview (Copilot)",
                    description="GitHub Copilot's o1 preview model",
                    context_length=128000,
                    supports_tools=False,  # o1 doesn't support tools yet
                    cost_per_input_token=0.0,
                    cost_per_output_token=0.0,
                ),
                ModelInfo(
                    id="o1-mini",
                    name="o1 Mini (Copilot)",
                    description="GitHub Copilot's o1 mini model",
                    context_length=128000,
                    supports_tools=False,
                    cost_per_input_token=0.0,
                    cost_per_output_token=0.0,
                ),
                # Additional OpenAI models available through GitHub Copilot
                ModelInfo(
                    id="gpt-4",
                    name="GPT-4 (Copilot)",
                    description="GitHub Copilot's GPT-4 model",
                    context_length=8192,
                    supports_tools=True,
                    cost_per_input_token=0.0,
                    cost_per_output_token=0.0,
                ),
                ModelInfo(
                    id="gpt-3.5-turbo",
                    name="GPT-3.5 Turbo (Copilot)",
                    description="GitHub Copilot's GPT-3.5 Turbo model",
                    context_length=16385,
                    supports_tools=True,
                    cost_per_input_token=0.0,
                    cost_per_output_token=0.0,
                ),
            ]
        )
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send chat request to GitHub Copilot."""
        # Get access token
        access_token = await self._auth.get_access_token()
        if not access_token:
            raise RuntimeError("GitHub Copilot authentication required")
        
        # Prepare headers
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "Openai-Intent": "conversation-edits",
            "User-Agent": "GitHubCopilotChat/0.26.7",
            "Editor-Version": "vscode/1.99.3",
            "Editor-Plugin-Version": "copilot-chat/0.26.7",
        }
        
        # Check if this is an agent call (has tool/assistant messages)
        is_agent_call = any(
            msg.role in ["tool", "assistant"] 
            for msg in request.messages 
            if hasattr(msg, 'role')
        )
        
        if is_agent_call:
            headers["X-Initiator"] = "agent"
        else:
            headers["X-Initiator"] = "user"
        
        # Convert messages to OpenAI format
        messages = []
        for msg in request.messages:
            openai_msg = {
                "role": msg.role,
                "content": msg.content,
            }
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                openai_msg["tool_calls"] = msg.tool_calls
            messages.append(openai_msg)
        
        # Prepare request payload
        payload = {
            "model": request.model,
            "messages": messages,
            "stream": request.stream or False,
        }
        
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        
        if request.tools:
            payload["tools"] = request.tools
        
        try:
            # Use GitHub Copilot's OpenAI-compatible endpoint
            async with httpx.AsyncClient(timeout=60.0) as client:
                self._log.info("Sending request to GitHub Copilot", {
                    "model": request.model,
                    "message_count": len(messages),
                    "has_tools": bool(request.tools)
                })
                
                response = await client.post(
                    "https://api.githubcopilot.com/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if not response.is_success:
                    error_text = await response.aread()
                    self._log.error("GitHub Copilot API error", {
                        "status": response.status_code,
                        "response": error_text.decode('utf-8')[:500]
                    })
                    raise httpx.HTTPStatusError(
                        f"GitHub Copilot API error: {response.status_code}",
                        request=response.request,
                        response=response
                    )
                
                response.raise_for_status()
                
                data = response.json()
                
                if request.stream:
                    # Handle streaming response (simplified)
                    content = ""
                    tool_calls = []
                    # In a real implementation, you'd handle SSE streaming
                    choice = data.get("choices", [{}])[0]
                    if choice.get("delta", {}).get("content"):
                        content = choice["delta"]["content"]
                    
                    return ChatResponse(
                        content=content,
                        tool_calls=tool_calls,
                    )
                else:
                    # Handle regular response
                    choice = data.get("choices", [{}])[0]
                    message = choice.get("message", {})
                    content = message.get("content", "")
                    tool_calls = message.get("tool_calls", [])
                    
                    # Convert tool calls to our format
                    tool_calls_dict = []
                    for tool_call in tool_calls:
                        tool_calls_dict.append({
                            "id": tool_call.get("id"),
                            "type": tool_call.get("type"),
                            "function": tool_call.get("function", {}),
                        })
                    
                    usage = data.get("usage")
                    if usage:
                        usage = {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0),
                        }
                    
                    return ChatResponse(
                        content=content,
                        tool_calls=tool_calls_dict,
                        usage=usage,
                        finish_reason=choice.get("finish_reason"),
                    )
        
        except Exception as e:
            raise RuntimeError(f"GitHub Copilot API error: {e}")
    
    async def is_authenticated(self) -> bool:
        """Check if GitHub Copilot is authenticated."""
        return await self._auth.is_authenticated()
    
    async def authenticate(self, **kwargs) -> bool:
        """Authenticate with GitHub Copilot using device flow."""
        try:
            # This would typically be called from the CLI
            # The actual device flow is handled in the CLI auth command
            return await self.is_authenticated()
        except Exception:
            return False
    
    async def start_device_flow(self) -> Dict[str, any]:
        """Start device authorization flow."""
        result = await self._auth.start_device_flow()
        return {
            "device": result.device,
            "user": result.user,
            "verification": result.verification,
            "interval": result.interval,
            "expiry": result.expiry,
        }
    
    async def poll_device_flow(self, device_code: str) -> str:
        """Poll device authorization flow."""
        success = await self._auth.complete_device_flow(device_code)
        if success:
            # Check if we actually got the tokens
            if await self.is_authenticated():
                return "complete"
            else:
                return "pending"
        else:
            return "failed"


# Error classes
class DeviceCodeError(NamedError):
    """Device code error."""
    pass


class TokenExchangeError(NamedError):
    """Token exchange error."""
    pass


class AuthenticationError(NamedError):
    """Authentication error."""
    pass


class CopilotTokenError(NamedError):
    """Copilot token error."""
    pass