"""Anthropic provider implementation."""

import os
from typing import Optional

import anthropic
from anthropic import AsyncAnthropic

from .provider import Provider, ProviderInfo, ModelInfo, ChatRequest, ChatResponse


class AnthropicProvider(Provider):
    """Anthropic provider implementation."""
    
    def __init__(self):
        super().__init__("anthropic")
        self._client: Optional[AsyncAnthropic] = None
    
    async def _get_client(self) -> AsyncAnthropic:
        """Get Anthropic client."""
        if self._client is None:
            # First try stored credentials
            from ..auth import Auth
            auth_info = await Auth.get("anthropic")
            
            api_key = None
            if auth_info and auth_info.type == "api":
                api_key = auth_info.key
            else:
                # Fallback to environment variable
                api_key = os.getenv("ANTHROPIC_API_KEY")
            
            if not api_key:
                raise ValueError("No Anthropic API key found in stored credentials or ANTHROPIC_API_KEY environment variable")
            
            self._client = AsyncAnthropic(api_key=api_key)
        return self._client
    
    async def get_info(self) -> ProviderInfo:
        """Get provider information."""
        return ProviderInfo(
            id=self.id,
            name="Anthropic",
            description="Anthropic's Claude models",
            requires_auth=True,
            auth_url="https://console.anthropic.com/",
            models=[
                ModelInfo(
                    id="claude-3-5-sonnet-20241022",
                    name="Claude 3.5 Sonnet",
                    description="Most intelligent model, best for complex tasks",
                    context_length=200000,
                    supports_tools=True,
                    cost_per_input_token=0.000003,
                    cost_per_output_token=0.000015,
                ),
                ModelInfo(
                    id="claude-3-haiku-20240307",
                    name="Claude 3 Haiku",
                    description="Fastest model, good for simple tasks",
                    context_length=200000,
                    supports_tools=True,
                    cost_per_input_token=0.00000025,
                    cost_per_output_token=0.00000125,
                ),
                ModelInfo(
                    id="claude-3-opus-20240229",
                    name="Claude 3 Opus",
                    description="Most powerful model for highly complex tasks",
                    context_length=200000,
                    supports_tools=True,
                    cost_per_input_token=0.000015,
                    cost_per_output_token=0.000075,
                ),
            ]
        )
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send chat request to Anthropic."""
        client = await self._get_client()
        
        # Convert messages to Anthropic format
        messages = []
        system_message = None
        
        for msg in request.messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })
        
        # Prepare request
        kwargs = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
        }
        
        if system_message:
            kwargs["system"] = system_message
        
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        
        if request.tools:
            kwargs["tools"] = request.tools
        
        if request.stream:
            kwargs["stream"] = True
        
        try:
            response = await client.messages.create(**kwargs)
            
            if request.stream:
                # Handle streaming response
                content = ""
                tool_calls = []
                async for chunk in response:
                    if chunk.type == "content_block_delta":
                        if hasattr(chunk.delta, 'text'):
                            content += chunk.delta.text
                    elif chunk.type == "content_block_start":
                        if hasattr(chunk.content_block, 'type') and chunk.content_block.type == "tool_use":
                            tool_calls.append({
                                "id": chunk.content_block.id,
                                "type": "function",
                                "function": {
                                    "name": chunk.content_block.name,
                                    "arguments": chunk.content_block.input,
                                }
                            })
                
                return ChatResponse(
                    content=content,
                    tool_calls=tool_calls,
                )
            else:
                # Handle regular response
                content = ""
                tool_calls = []
                
                for content_block in response.content:
                    if content_block.type == "text":
                        content += content_block.text
                    elif content_block.type == "tool_use":
                        tool_calls.append({
                            "id": content_block.id,
                            "type": "function",
                            "function": {
                                "name": content_block.name,
                                "arguments": content_block.input,
                            }
                        })
                
                usage = None
                if hasattr(response, 'usage'):
                    usage = {
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                    }
                
                return ChatResponse(
                    content=content,
                    tool_calls=tool_calls,
                    usage=usage,
                    finish_reason=response.stop_reason,
                )
        
        except Exception as e:
            raise RuntimeError(f"Anthropic API error: {e}")

    async def chat_streaming(self, request: ChatRequest):
        """Send streaming chat request to Anthropic."""
        client = await self._get_client()

        # Convert messages to Anthropic format
        messages = []
        for msg in request.messages:
            if msg.role == "system":
                # System messages are handled separately in Anthropic
                continue
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # Prepare request parameters
        kwargs = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
            "stream": True
        }

        # Add system message if present
        system_messages = [msg.content for msg in request.messages if msg.role == "system"]
        if system_messages:
            kwargs["system"] = "\n\n".join(system_messages)

        if request.temperature is not None:
            kwargs["temperature"] = request.temperature

        if request.tools:
            kwargs["tools"] = request.tools

        try:
            response = await client.messages.create(**kwargs)

            content = ""
            tool_calls = []

            async for chunk in response:
                if chunk.type == "content_block_delta":
                    if hasattr(chunk.delta, 'text'):
                        text_content = chunk.delta.text
                        content += text_content
                        yield {
                            "type": "content",
                            "content": text_content
                        }
                elif chunk.type == "content_block_start":
                    if hasattr(chunk.content_block, 'type') and chunk.content_block.type == "tool_use":
                        tool_calls.append({
                            "id": chunk.content_block.id,
                            "type": "function",
                            "function": {
                                "name": chunk.content_block.name,
                                "arguments": chunk.content_block.input,
                            }
                        })
                elif chunk.type == "message_stop":
                    # Send tool calls if any
                    if tool_calls:
                        yield {
                            "type": "tool_calls",
                            "tool_calls": tool_calls
                        }

                    # Send completion
                    yield {
                        "type": "complete",
                        "usage": {
                            "prompt_tokens": getattr(chunk, 'input_tokens', 0),
                            "completion_tokens": getattr(chunk, 'output_tokens', 0),
                            "total_tokens": getattr(chunk, 'input_tokens', 0) + getattr(chunk, 'output_tokens', 0)
                        }
                    }
                    break

        except Exception as e:
            yield {
                "type": "error",
                "content": f"Anthropic streaming error: {str(e)}"
            }

    async def is_authenticated(self) -> bool:
        """Check if Anthropic is authenticated."""
        try:
            client = await self._get_client()
            # Try a simple API call to check authentication
            await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except Exception:
            return False
    
    async def authenticate(self, api_key: str) -> bool:
        """Authenticate with Anthropic."""
        try:
            self._client = AsyncAnthropic(api_key=api_key)
            await self._client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            
            # Save API key to environment
            os.environ["ANTHROPIC_API_KEY"] = api_key
            return True
        except Exception:
            self._client = None
            return False