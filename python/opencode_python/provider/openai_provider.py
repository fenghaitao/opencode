"""OpenAI provider implementation."""

import os
from typing import Optional

import openai
from openai import AsyncOpenAI

from .provider import Provider, ProviderInfo, ModelInfo, ChatRequest, ChatResponse, ChatMessage


class OpenAIProvider(Provider):
    """OpenAI provider implementation."""
    
    def __init__(self):
        super().__init__("openai")
        self._client: Optional[AsyncOpenAI] = None
    
    async def _get_client(self) -> AsyncOpenAI:
        """Get OpenAI client."""
        if self._client is None:
            # First try stored credentials
            from ..auth import Auth
            auth_info = await Auth.get("openai")
            
            api_key = None
            if auth_info and auth_info.type == "api":
                api_key = auth_info.key
            else:
                # Fallback to environment variable
                api_key = os.getenv("OPENAI_API_KEY")
            
            if not api_key:
                raise ValueError("No OpenAI API key found in stored credentials or OPENAI_API_KEY environment variable")
            
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client
    
    async def get_info(self) -> ProviderInfo:
        """Get provider information."""
        return ProviderInfo(
            id=self.id,
            name="OpenAI",
            description="OpenAI's GPT models",
            requires_auth=True,
            auth_url="https://platform.openai.com/api-keys",
            models=[
                ModelInfo(
                    id="gpt-4",
                    name="GPT-4",
                    description="Most capable model, best for complex tasks",
                    context_length=8192,
                    supports_tools=True,
                    cost_per_input_token=0.00003,
                    cost_per_output_token=0.00006,
                ),
                ModelInfo(
                    id="gpt-4-turbo",
                    name="GPT-4 Turbo",
                    description="Latest GPT-4 model with improved performance",
                    context_length=128000,
                    supports_tools=True,
                    cost_per_input_token=0.00001,
                    cost_per_output_token=0.00003,
                ),
                ModelInfo(
                    id="gpt-3.5-turbo",
                    name="GPT-3.5 Turbo",
                    description="Fast and efficient model for most tasks",
                    context_length=16385,
                    supports_tools=True,
                    cost_per_input_token=0.0000005,
                    cost_per_output_token=0.0000015,
                ),
            ]
        )
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send chat request to OpenAI."""
        client = await self._get_client()
        
        # Convert messages
        messages = []
        for msg in request.messages:
            openai_msg = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.tool_calls:
                openai_msg["tool_calls"] = msg.tool_calls
            messages.append(openai_msg)
        
        # Prepare request
        kwargs = {
            "model": request.model,
            "messages": messages,
        }
        
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        
        if request.tools:
            kwargs["tools"] = request.tools
        
        if request.stream:
            kwargs["stream"] = True
        
        try:
            response = await client.chat.completions.create(**kwargs)
            
            if request.stream:
                # Handle streaming response
                content = ""
                tool_calls = []
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            content += delta.content
                        if delta.tool_calls:
                            tool_calls.extend(delta.tool_calls)
                
                return ChatResponse(
                    content=content,
                    tool_calls=tool_calls,
                )
            else:
                # Handle regular response
                choice = response.choices[0]
                content = choice.message.content or ""
                tool_calls = choice.message.tool_calls or []
                
                # Convert tool calls to dict format
                tool_calls_dict = []
                for tool_call in tool_calls:
                    tool_calls_dict.append({
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        }
                    })
                
                usage = None
                if response.usage:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                
                return ChatResponse(
                    content=content,
                    tool_calls=tool_calls_dict,
                    usage=usage,
                    finish_reason=choice.finish_reason,
                )
        
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {e}")
    
    async def is_authenticated(self) -> bool:
        """Check if OpenAI is authenticated."""
        try:
            client = await self._get_client()
            # Try a simple API call to check authentication
            await client.models.list()
            return True
        except Exception:
            return False
    
    async def authenticate(self, api_key: str) -> bool:
        """Authenticate with OpenAI."""
        try:
            self._client = AsyncOpenAI(api_key=api_key)
            await self._client.models.list()
            
            # Save API key to environment (in a real implementation, 
            # this would be saved securely)
            os.environ["OPENAI_API_KEY"] = api_key
            return True
        except Exception:
            self._client = None
            return False