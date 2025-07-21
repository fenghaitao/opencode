"""FastAPI server implementation for OpenCode Python."""

import asyncio
import json
from typing import Dict, List, Optional, Any

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..app import App
from ..config import Config
from ..session import Session, Mode
from ..provider import ProviderManager, OpenAIProvider, AnthropicProvider, GitHubCopilotProvider
from ..provider.provider import ChatRequest, ChatMessage
from ..util.log import Log


class ServerConfig(BaseModel):
    """Server configuration."""
    port: int = 4096
    host: str = "127.0.0.1"
    reload: bool = False


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    message: str
    data: Optional[Dict[str, Any]] = None


class SessionCreateRequest(BaseModel):
    """Request to create a new session."""
    mode: Optional[str] = "default"


class SessionInitRequest(BaseModel):
    """Request to initialize a session."""
    message_id: str
    provider_id: str
    model_id: str


class SessionSummarizeRequest(BaseModel):
    """Request to summarize a session."""
    provider_id: str
    model_id: str


class ChatMessageRequest(BaseModel):
    """Chat message request."""
    message_id: Optional[str] = None
    provider_id: str
    model_id: str
    mode: Optional[str] = None
    tools: Optional[Dict[str, bool]] = None
    parts: List[Dict[str, Any]]


class LogRequest(BaseModel):
    """Log request."""
    service: str
    level: str
    message: str
    extra: Optional[Dict[str, Any]] = None


class Server:
    """OpenCode FastAPI server."""
    
    def __init__(self, config: ServerConfig):
        self.config = config
        self.app = FastAPI(
            title="OpenCode",
            description="OpenCode API Server",
            version="1.0.0",
        )
        self._log = Log.create({"service": "server"})
        self._setup_middleware()
        self._setup_routes()
    
    def _setup_middleware(self):
        """Setup FastAPI middleware."""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure as needed
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Request logging middleware
        @self.app.middleware("http")
        async def log_requests(request, call_next):
            start_time = asyncio.get_event_loop().time()
            self._log.info("request", {
                "method": request.method,
                "path": request.url.path,
            })
            
            response = await call_next(request)
            
            duration = (asyncio.get_event_loop().time() - start_time) * 1000
            self._log.info("response", {
                "duration": f"{duration:.2f}ms",
                "status": response.status_code,
            })
            
            return response
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {"message": "OpenCode API Server", "version": "1.0.0"}
        
        @self.app.get("/doc")
        async def openapi_spec():
            """Get OpenAPI specification."""
            return self.app.openapi()
        
        @self.app.get("/app")
        async def get_app_info():
            """Get application information."""
            async def get_info():
                app_info = App.info()
                return {
                    "hostname": app_info.hostname,
                    "git": app_info.git,
                    "path": app_info.path,
                    "time": app_info.time,
                }
            
            return await App.provide(".", lambda _: get_info())
        
        @self.app.post("/app/init")
        async def initialize_app():
            """Initialize the application."""
            async def init():
                await App.initialize()
                return True
            
            return await App.provide(".", lambda _: init())
        
        @self.app.get("/config")
        async def get_config():
            """Get configuration."""
            async def get_cfg():
                config = await Config.get()
                return config.model_dump()
            
            return await App.provide(".", lambda _: get_cfg())
        
        @self.app.get("/config/providers")
        async def get_providers():
            """Get available providers and models."""
            async def get_provider_info():
                # Register providers
                ProviderManager.register(OpenAIProvider())
                ProviderManager.register(AnthropicProvider())
                ProviderManager.register(GitHubCopilotProvider())
                
                providers = []
                default_models = {}
                
                for provider in ProviderManager.list():
                    try:
                        provider_info = await provider.get_info()
                        is_authenticated = await provider.is_authenticated()
                        
                        provider_data = {
                            "id": provider_info.id,
                            "name": provider_info.name,
                            "description": provider_info.description,
                            "requires_auth": provider_info.requires_auth,
                            "auth_url": provider_info.auth_url,
                            "authenticated": is_authenticated,
                            "models": {}
                        }
                        
                        # Add models
                        for model in provider_info.models:
                            provider_data["models"][model.id] = {
                                "id": model.id,
                                "name": model.name,
                                "description": model.description,
                                "context_length": model.context_length,
                                "supports_tools": model.supports_tools,
                                "supports_streaming": model.supports_streaming,
                                "cost_per_input_token": model.cost_per_input_token,
                                "cost_per_output_token": model.cost_per_output_token,
                            }
                        
                        providers.append(provider_data)
                        
                        # Set default model (first model)
                        if provider_info.models:
                            default_models[provider_info.id] = provider_info.models[0].id
                    
                    except Exception as e:
                        self._log.error("Error loading provider", {"provider": provider.id, "error": str(e)})
                
                return {
                    "providers": providers,
                    "default": default_models
                }
            
            return await App.provide(".", lambda _: get_provider_info())
        
        @self.app.get("/session")
        async def list_sessions():
            """List all sessions."""
            async def get_sessions():
                sessions = []
                async for session in Session.list():
                    sessions.append(session.model_dump())
                return sessions
            
            return await App.provide(".", lambda _: get_sessions())
        
        @self.app.post("/session")
        async def create_session(request: SessionCreateRequest):
            """Create a new session."""
            async def create():
                session = await Session.create(request.mode or "default")
                return session.model_dump()
            
            return await App.provide(".", lambda _: create())
        
        @self.app.delete("/session/{session_id}")
        async def delete_session(session_id: str):
            """Delete a session."""
            async def delete():
                await Session.delete(session_id)
                return True
            
            return await App.provide(".", lambda _: delete())
        
        @self.app.post("/session/{session_id}/init")
        async def initialize_session(session_id: str, request: SessionInitRequest):
            """Initialize a session with AGENTS.md analysis."""
            async def init():
                # This would implement the initialization logic
                # For now, return success
                return True
            
            return await App.provide(".", lambda _: init())
        
        @self.app.post("/session/{session_id}/abort")
        async def abort_session(session_id: str):
            """Abort a session."""
            async def abort():
                # This would implement session abortion
                return True
            
            return await App.provide(".", lambda _: abort())
        
        @self.app.post("/session/{session_id}/share")
        async def share_session(session_id: str):
            """Share a session."""
            async def share():
                share_url = await Session.share(session_id)
                session = await Session.get(session_id)
                return session.model_dump()
            
            return await App.provide(".", lambda _: share())
        
        @self.app.delete("/session/{session_id}/share")
        async def unshare_session(session_id: str):
            """Unshare a session."""
            async def unshare():
                await Session.unshare(session_id)
                session = await Session.get(session_id)
                return session.model_dump()
            
            return await App.provide(".", lambda _: unshare())
        
        @self.app.post("/session/{session_id}/summarize")
        async def summarize_session(session_id: str, request: SessionSummarizeRequest):
            """Summarize a session."""
            async def summarize():
                # This would implement session summarization
                return True
            
            return await App.provide(".", lambda _: summarize())
        
        @self.app.get("/session/{session_id}/message")
        async def get_session_messages(session_id: str):
            """Get messages for a session."""
            async def get_messages():
                messages = await Session.get_messages(session_id)
                return [msg.model_dump() for msg in messages]
            
            return await App.provide(".", lambda _: get_messages())
        
        @self.app.post("/session/{session_id}/message")
        async def send_message(session_id: str, request: ChatMessageRequest):
            """Send a message to a session."""
            async def chat():
                # Register providers
                ProviderManager.register(OpenAIProvider())
                ProviderManager.register(AnthropicProvider())
                ProviderManager.register(GitHubCopilotProvider())
                
                # Get provider
                provider = ProviderManager.get(request.provider_id)
                if not provider:
                    raise HTTPException(status_code=400, detail=f"Provider {request.provider_id} not found")
                
                # Check authentication
                if not await provider.is_authenticated():
                    raise HTTPException(status_code=401, detail=f"Not authenticated with {request.provider_id}")
                
                # Extract message content from parts
                message_content = ""
                for part in request.parts:
                    if part.get("type") == "text":
                        message_content += part.get("text", "")
                
                if not message_content.strip():
                    raise HTTPException(status_code=400, detail="No message content provided")
                
                # Create chat request
                chat_request = ChatRequest(
                    messages=[
                        ChatMessage(role="user", content=message_content)
                    ],
                    model=request.model_id,
                    max_tokens=4096
                )
                
                # Send to provider
                response = await provider.chat(chat_request)
                
                # Save to session (simplified)
                session = await Session.get(session_id)
                
                # Return response
                return {
                    "id": request.message_id or f"msg-{session_id}",
                    "role": "assistant",
                    "content": response.content,
                    "usage": response.usage,
                    "session_id": session_id,
                }
            
            return await App.provide(".", lambda _: chat())
        
        @self.app.get("/event")
        async def event_stream():
            """Server-sent events stream."""
            async def generate():
                # This would implement real-time event streaming
                # For now, send a simple heartbeat
                while True:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
                    await asyncio.sleep(30)
            
            return StreamingResponse(generate(), media_type="text/plain")
        
        @self.app.get("/find")
        async def find_text(pattern: str):
            """Find text in files."""
            async def search():
                # This would implement file search
                # For now, return empty results
                return []
            
            return await App.provide(".", lambda _: search())
        
        @self.app.get("/find/file")
        async def find_files(query: str):
            """Find files."""
            async def search():
                # This would implement file finding
                # For now, return empty results
                return []
            
            return await App.provide(".", lambda _: search())
        
        @self.app.get("/find/symbol")
        async def find_symbols(query: str):
            """Find workspace symbols."""
            async def search():
                # This would implement symbol search
                # For now, return empty results
                return []
            
            return await App.provide(".", lambda _: search())
        
        @self.app.get("/file")
        async def read_file(path: str):
            """Read a file."""
            async def read():
                # This would implement file reading
                # For now, return placeholder
                return {
                    "type": "raw",
                    "content": f"File content for {path}"
                }
            
            return await App.provide(".", lambda _: read())
        
        @self.app.get("/file/status")
        async def get_file_status():
            """Get file status."""
            async def status():
                # This would implement file status
                # For now, return empty
                return []
            
            return await App.provide(".", lambda _: status())
        
        @self.app.post("/log")
        async def write_log(request: LogRequest):
            """Write a log entry."""
            logger = Log.create({"service": request.service})
            
            if request.level == "debug":
                logger.debug(request.message, request.extra)
            elif request.level == "info":
                logger.info(request.message, request.extra)
            elif request.level == "error":
                logger.error(request.message, request.extra)
            elif request.level == "warn":
                logger.warn(request.message, request.extra)
            
            return True
        
        @self.app.get("/mode")
        async def list_modes():
            """List all modes."""
            async def get_modes():
                modes = await Mode.list()
                return [mode.model_dump() for mode in modes]
            
            return await App.provide(".", lambda _: get_modes())
    
    async def serve(self):
        """Serve the application."""
        import uvicorn
        
        self._log.info("Starting server", {
            "host": self.config.host,
            "port": self.config.port,
        })
        
        config = uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            reload=self.config.reload,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    def run(self):
        """Run the server (blocking)."""
        self._log.info("Starting server", {
            "host": self.config.host,
            "port": self.config.port,
        })
        
        uvicorn.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            reload=self.config.reload,
            log_level="info"
        )
    
    @classmethod
    async def check_providers(cls) -> bool:
        """Check if any providers are available."""
        async def check():
            # Register providers
            ProviderManager.register(OpenAIProvider())
            ProviderManager.register(AnthropicProvider())
            ProviderManager.register(GitHubCopilotProvider())
            
            providers = ProviderManager.list()
            return len(providers) > 0
        
        return await App.provide(".", lambda _: check())