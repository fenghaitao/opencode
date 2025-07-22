"""Session management for chat conversations."""

import json
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Any

from pydantic import BaseModel

from ..app import App
from ..util.log import Log
from ..tools import ToolRegistry, ToolContext, ToolResult
from ..provider.provider import ChatRequest, ChatMessage as ProviderChatMessage, ChatResponse, StreamingChatResponse
from ..provider import ProviderManager, OpenAIProvider, AnthropicProvider, GitHubCopilotProvider
from .message import Message, MessagePart
from .mode import Mode
from .system import SystemPrompt


class SessionInfo(BaseModel):
    """Session information."""
    
    id: str
    title: Optional[str] = None
    created: datetime
    updated: datetime
    message_count: int = 0
    mode: str = "default"


class SessionChatRequest(BaseModel):
    """Request to chat with AI in a session context."""
    
    session_id: str
    provider_id: str
    model_id: str
    mode: str = "default"
    message_content: str
    tools_enabled: Optional[Dict[str, bool]] = None


class SessionChatResponse(BaseModel):
    """Response from session chat."""
    
    content: str
    tool_calls: List[Dict[str, Any]] = []
    usage: Optional[Dict[str, Any]] = None


class StreamingSessionResponse:
    """Streaming response from session chat."""
    
    def __init__(self, session_id: str, message_id: str):
        self.session_id = session_id
        self.message_id = message_id
        self.content = ""
        self.tool_calls = []
        self.usage = None
        self.is_complete = False
        self._chunks = []
        self._processing_started = False
        self._processing_complete = False
    
    def __aiter__(self):
        """Async iterator for streaming chunks."""
        return self
    
    async def __anext__(self):
        """Get next chunk."""
        # Wait for processing to start
        while not self._processing_started and not self.is_complete:
            await asyncio.sleep(0.01)
            
        while True:
            if self._chunks:
                return self._chunks.pop(0)
            elif self.is_complete:
                raise StopAsyncIteration
            else:
                # Wait for more chunks or completion
                await asyncio.sleep(0.01)
    
    def add_chunk(self, chunk_type: str, content: str = "", **kwargs):
        """Add a streaming chunk."""
        chunk = {
            "type": chunk_type,
            "content": content,
            **kwargs
        }
        self._chunks.append(chunk)
        
        if chunk_type == "content":
            self.content += content
    
    def complete(self, usage: Optional[Dict[str, Any]] = None):
        """Mark the response as complete."""
        self.usage = usage
        self.is_complete = True
        self.add_chunk("complete")


class Session:
    """Session management."""
    
    _log = Log.create({"service": "session"})
    _providers_registered = False
    
    @classmethod
    def _ensure_providers_registered(cls):
        """Ensure providers are registered."""
        if not cls._providers_registered:
            ProviderManager.register(OpenAIProvider())
            ProviderManager.register(AnthropicProvider())
            ProviderManager.register(GitHubCopilotProvider())
            cls._providers_registered = True
    
    @classmethod
    async def create(cls, mode: str = "default") -> SessionInfo:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        now = datetime.now()
        
        session_info = SessionInfo(
            id=session_id,
            created=now,
            updated=now,
            mode=mode
        )
        
        # Create session directory
        app_info = App.info()
        session_dir = Path(app_info.path["data"]) / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save session info
        info_file = session_dir / "info.json"
        with open(info_file, 'w') as f:
            json.dump(session_info.model_dump(mode='json'), f, indent=2, default=str)
        
        cls._log.info("Created session", {"session_id": session_id, "mode": mode})
        return session_info
    
    @classmethod
    async def get(cls, session_id: str) -> Optional[SessionInfo]:
        """Get session by ID."""
        app_info = App.info()
        session_dir = Path(app_info.path["data"]) / "sessions" / session_id
        info_file = session_dir / "info.json"
        
        if not info_file.exists():
            return None
        
        try:
            with open(info_file, 'r') as f:
                data = json.load(f)
            return SessionInfo(**data)
        except Exception as e:
            cls._log.error("Failed to load session", {"session_id": session_id, "error": str(e)})
            return None
    
    @classmethod
    async def list(cls) -> AsyncGenerator[SessionInfo, None]:
        """List all sessions, newest first."""
        app_info = App.info()
        sessions_dir = Path(app_info.path["data"]) / "sessions"
        
        if not sessions_dir.exists():
            return
        
        # Get all session directories
        session_dirs = [d for d in sessions_dir.iterdir() if d.is_dir()]
        
        # Sort by modification time (newest first)
        session_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        
        for session_dir in session_dirs:
            info_file = session_dir / "info.json"
            if info_file.exists():
                try:
                    with open(info_file, 'r') as f:
                        data = json.load(f)
                    yield SessionInfo(**data)
                except Exception:
                    continue
    
    @classmethod
    async def delete(cls, session_id: str) -> bool:
        """Delete a session."""
        app_info = App.info()
        session_dir = Path(app_info.path["data"]) / "sessions" / session_id
        
        if not session_dir.exists():
            return False
        
        try:
            import shutil
            shutil.rmtree(session_dir)
            cls._log.info("Deleted session", {"session_id": session_id})
            return True
        except Exception as e:
            cls._log.error("Failed to delete session", {"session_id": session_id, "error": str(e)})
            return False
    
    @classmethod
    async def add_message(cls, session_id: str, message: Message) -> None:
        """Add a message to a session."""
        app_info = App.info()
        session_dir = Path(app_info.path["data"]) / "sessions" / session_id
        
        if not session_dir.exists():
            raise ValueError(f"Session {session_id} not found")
        
        # Save message
        messages_dir = session_dir / "messages"
        messages_dir.mkdir(exist_ok=True)
        
        message_file = messages_dir / f"{message.id}.json"
        with open(message_file, 'w') as f:
            json.dump(message.model_dump(mode='json'), f, indent=2, default=str)
        
        # Update session info
        await cls._update_session_info(session_id)
    
    @classmethod
    async def get_messages(cls, session_id: str) -> List[Message]:
        """Get all messages in a session."""
        app_info = App.info()
        session_dir = Path(app_info.path["data"]) / "sessions" / session_id
        messages_dir = session_dir / "messages"
        
        if not messages_dir.exists():
            return []
        
        messages = []
        message_files = list(messages_dir.glob("*.json"))
        
        for message_file in message_files:
            try:
                with open(message_file, 'r') as f:
                    data = json.load(f)
                messages.append(Message(**data))
            except Exception:
                continue
        
        # Sort by timestamp
        messages.sort(key=lambda m: m.timestamp)
        return messages
    
    @classmethod
    async def chat(cls, request: SessionChatRequest) -> SessionChatResponse:
        """Process a chat request with full system prompt and tool integration (non-streaming)."""
        # For backward compatibility, convert streaming to non-streaming
        streaming_response = await cls.chat_streaming(request)
        content = ""
        tool_calls = []
        usage = None
        
        async for chunk in streaming_response:
            if chunk["type"] == "content":
                content += chunk["content"]
            elif chunk["type"] == "tool_calls":
                tool_calls = chunk.get("tool_calls", [])
            elif chunk["type"] == "complete":
                usage = chunk.get("usage")
        
        return SessionChatResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage
        )
    
    @classmethod
    async def chat_streaming(cls, request: SessionChatRequest) -> StreamingSessionResponse:
        """Process a streaming chat request with full system prompt and tool integration."""
        # Ensure providers are registered
        cls._ensure_providers_registered()
        
        cls._log.info("Streaming chat request", {
            "session_id": request.session_id,
            "provider": request.provider_id,
            "model": request.model_id,
            "mode": request.mode
        })
        
        # Create streaming response
        streaming_response = StreamingSessionResponse(request.session_id, "temp-message-id")
        
        # Define async processing function
        async def _process_streaming():
            try:
                # Mark processing as started
                streaming_response._processing_started = True
                
                # Get mode configuration
                mode = await Mode.get(request.mode)
                
                # Build system prompts
                system_prompts = []
                
                # Add provider-specific prompts
                system_prompts.extend(SystemPrompt.provider(request.model_id))
                
                # Add environment context
                system_prompts.extend(await SystemPrompt.environment())
                
                # Add custom instructions
                system_prompts.extend(await SystemPrompt.custom())
                
                # Add mode-specific prompt
                if mode.system_prompt:
                    system_prompts.append(mode.system_prompt)
                
                # Combine system prompts (max 2 for caching)
                if len(system_prompts) > 2:
                    combined_system = [system_prompts[0], "\n\n".join(system_prompts[1:])]
                else:
                    combined_system = system_prompts
                
                # Get available tools
                available_tools = ToolRegistry.list_available(mode.tools)
                tools_spec = ToolRegistry.to_openai_format(available_tools) if available_tools else None
                
                # Create messages for the provider
                messages = []
                
                # Add system messages
                for system_msg in combined_system:
                    if system_msg.strip():
                        messages.append(ProviderChatMessage(role="system", content=system_msg))
                
                # Add user message
                messages.append(ProviderChatMessage(role="user", content=request.message_content))
                
                # Get provider and send request
                provider = ProviderManager.get(request.provider_id)
                if not provider:
                    raise Exception(f"Provider {request.provider_id} not found")
                
                if not await provider.is_authenticated():
                    raise Exception(f"Not authenticated with {request.provider_id}")
                
                # Create chat request with streaming enabled
                chat_request = ChatRequest(
                    messages=messages,
                    model=request.model_id,
                    max_tokens=4096,
                    tools=tools_spec,
                    stream=True
                )
                
                # Check if provider supports streaming
                if hasattr(provider, 'chat_streaming'):
                    # Use streaming if available
                    async for chunk in provider.chat_streaming(chat_request):
                        if chunk.get("type") == "content":
                            streaming_response.add_chunk("content", chunk.get("content", ""))
                        elif chunk.get("type") == "tool_calls":
                            streaming_response.tool_calls = chunk.get("tool_calls", [])
                            streaming_response.add_chunk("tool_calls", tool_calls=chunk.get("tool_calls", []))
                        elif chunk.get("type") == "complete":
                            streaming_response.complete(chunk.get("usage"))
                            break
                else:
                    # Fallback to non-streaming
                    streaming_response.add_chunk("status", "Generating response...")
                    response = await provider.chat(chat_request)
                    
                    # Simulate streaming by breaking content into chunks
                    content = response.content
                    chunk_size = 20  # Smaller chunks for more visible streaming
                    for i in range(0, len(content), chunk_size):
                        chunk = content[i:i + chunk_size]
                        streaming_response.add_chunk("content", chunk)
                        # Longer delay to make streaming more visible
                        await asyncio.sleep(0.1)
                    
                    # Handle tool calls
                    if response.tool_calls:
                        streaming_response.tool_calls = response.tool_calls
                        streaming_response.add_chunk("tool_calls", tool_calls=response.tool_calls)
                        
                        # Execute tools and stream results
                        tool_results = await cls._execute_tool_calls_streaming(
                            response.tool_calls,
                            request.session_id,
                            "temp-message-id",
                            streaming_response
                        )
                    
                    streaming_response.complete(response.usage)
                    
            except Exception as e:
                cls._log.error("Chat error", {"error": str(e)})
                streaming_response.add_chunk("error", f"Error: {str(e)}")
                streaming_response.complete()
            finally:
                # Ensure processing is marked as started even if there's an error
                if not streaming_response._processing_started:
                    streaming_response._processing_started = True
        
        # Start the async processing task and store reference
        task = asyncio.create_task(_process_streaming())
        
        # Store task reference so it doesn't get garbage collected
        streaming_response._background_task = task
        
        return streaming_response
    
    @classmethod
    async def _execute_tool_calls(
        cls,
        tool_calls: List[Dict[str, Any]],
        session_id: str,
        message_id: str
    ) -> List[str]:
        """Execute tool calls and return results."""
        results = []
        
        for tool_call in tool_calls:
            try:
                function_name = tool_call.get("function", {}).get("name", "")
                arguments_str = tool_call.get("function", {}).get("arguments", "{}")
                
                # Parse arguments
                try:
                    arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                except json.JSONDecodeError:
                    arguments = {}
                
                # Create tool context
                abort_event = asyncio.Event()
                context = ToolContext(
                    session_id=session_id,
                    message_id=message_id,
                    abort_event=abort_event,
                    metadata_callback=lambda x: None  # TODO: Implement metadata handling
                )
                
                # Execute tool
                result = await ToolRegistry.execute_tool(function_name, arguments, context)
                results.append(f"[{function_name}] {result.output}")
                
            except Exception as e:
                results.append(f"[{function_name}] Error: {str(e)}")
        
        return results
    
    @classmethod
    async def _execute_tool_calls_streaming(
        cls,
        tool_calls: List[Dict[str, Any]],
        session_id: str,
        message_id: str,
        streaming_response: StreamingSessionResponse
    ) -> List[str]:
        """Execute tool calls with streaming updates."""
        results = []
        
        for tool_call in tool_calls:
            try:
                function_name = tool_call.get("function", {}).get("name", "")
                arguments_str = tool_call.get("function", {}).get("arguments", "{}")
                
                # Parse arguments
                try:
                    arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                except json.JSONDecodeError:
                    arguments = {}
                
                # Stream tool execution start
                streaming_response.add_chunk("tool_start", f"Executing {function_name}...")
                
                # Create tool context
                abort_event = asyncio.Event()
                context = ToolContext(
                    session_id=session_id,
                    message_id=message_id,
                    abort_event=abort_event,
                    metadata_callback=lambda x: None  # TODO: Implement metadata handling
                )
                
                # Execute tool
                result = await ToolRegistry.execute_tool(function_name, arguments, context)
                
                # Stream tool result
                tool_result = f"[{function_name}] {result.output}"
                streaming_response.add_chunk("tool_result", tool_result)
                results.append(tool_result)
                
            except Exception as e:
                error_msg = f"[{function_name}] Error: {str(e)}"
                streaming_response.add_chunk("tool_error", error_msg)
                results.append(error_msg)
        
        return results
    
    @classmethod
    async def share(cls, session_id: str) -> str:
        """Share a session and return share URL."""
        # This is a placeholder - would integrate with sharing service
        cls._log.info("Sharing session", {"session_id": session_id})
        return f"https://opencode.ai/s/{session_id[-8:]}"
    
    @classmethod
    async def _update_session_info(cls, session_id: str) -> None:
        """Update session info after changes."""
        session_info = await cls.get(session_id)
        if not session_info:
            return
        
        # Count messages
        messages = await cls.get_messages(session_id)
        session_info.message_count = len(messages)
        session_info.updated = datetime.now()
        
        # Generate title from first message if not set
        if not session_info.title and messages:
            first_message = messages[0]
            text_content = first_message.get_text_content()
            if text_content:
                # Use first 50 characters as title
                session_info.title = text_content[:50].strip()
                if len(text_content) > 50:
                    session_info.title += "..."
        
        # Save updated info
        app_info = App.info()
        session_dir = Path(app_info.path["data"]) / "sessions" / session_id
        info_file = session_dir / "info.json"
        
        with open(info_file, 'w') as f:
            json.dump(session_info.model_dump(mode='json'), f, indent=2, default=str)