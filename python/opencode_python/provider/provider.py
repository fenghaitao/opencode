"""Base provider interface and management."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from ..config import Config


class ModelInfo(BaseModel):
    """Information about an AI model."""
    
    id: str
    name: str
    description: str
    context_length: int
    supports_tools: bool = True
    supports_streaming: bool = True
    cost_per_input_token: Optional[float] = None
    cost_per_output_token: Optional[float] = None


class ProviderInfo(BaseModel):
    """Information about an AI provider."""
    
    id: str
    name: str
    description: str
    models: List[ModelInfo]
    requires_auth: bool = True
    auth_url: Optional[str] = None


class ChatMessage(BaseModel):
    """Chat message for provider API."""
    
    role: str  # "user", "assistant", "system"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatRequest(BaseModel):
    """Request to chat with AI provider."""
    
    messages: List[ChatMessage]
    model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[List[Dict[str, Any]]] = None
    stream: bool = False


class ChatResponse(BaseModel):
    """Response from AI provider."""
    
    content: str
    tool_calls: List[Dict[str, Any]] = []
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None


class Provider(ABC):
    """Base class for AI providers."""
    
    def __init__(self, provider_id: str):
        self.id = provider_id
    
    @abstractmethod
    async def get_info(self) -> ProviderInfo:
        """Get provider information."""
        pass
    
    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send chat request to provider."""
        pass
    
    @abstractmethod
    async def is_authenticated(self) -> bool:
        """Check if provider is authenticated."""
        pass
    
    @abstractmethod
    async def authenticate(self, **kwargs) -> bool:
        """Authenticate with provider."""
        pass


class ProviderManager:
    """Manages AI providers."""
    
    _providers: Dict[str, Provider] = {}
    
    @classmethod
    def register(cls, provider: Provider) -> None:
        """Register a provider."""
        cls._providers[provider.id] = provider
    
    @classmethod
    def get(cls, provider_id: str) -> Optional[Provider]:
        """Get a provider by ID."""
        return cls._providers.get(provider_id)
    
    @classmethod
    def list(cls) -> List[Provider]:
        """List all registered providers."""
        return list(cls._providers.values())
    
    @classmethod
    async def get_default_model(cls) -> Tuple[str, str]:
        """Get default provider and model."""
        config = await Config.get()
        
        if config.default_provider and config.default_model:
            return config.default_provider, config.default_model
        
        # Fallback to first available provider
        for provider in cls._providers.values():
            if await provider.is_authenticated():
                info = await provider.get_info()
                if info.models:
                    return provider.id, info.models[0].id
        
        # Default fallback
        return "openai", "gpt-4"
    
    @classmethod
    def parse_model(cls, model_string: str) -> Tuple[str, str]:
        """Parse provider/model string."""
        if "/" in model_string:
            provider_id, model_id = model_string.split("/", 1)
            return provider_id, model_id
        else:
            # Assume OpenAI if no provider specified
            return "openai", model_string