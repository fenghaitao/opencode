"""Session management for chat conversations."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

from pydantic import BaseModel

from ..app import App
from ..util.log import Log
from .message import Message, MessagePart
from .mode import Mode


class SessionInfo(BaseModel):
    """Session information."""
    
    id: str
    title: Optional[str] = None
    created: datetime
    updated: datetime
    message_count: int = 0
    mode: str = "default"


class ChatRequest(BaseModel):
    """Request to chat with AI."""
    
    session_id: str
    provider_id: str
    model_id: str
    mode: str
    parts: List[Dict]  # MessagePart data


class ChatResponse(BaseModel):
    """Response from chat."""
    
    parts: List[MessagePart]


class Session:
    """Session management."""
    
    _log = Log.create({"service": "session"})
    
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
    async def chat(cls, request: ChatRequest) -> ChatResponse:
        """Process a chat request."""
        # This is a placeholder - in a real implementation, this would:
        # 1. Load the session and mode
        # 2. Create a user message from the request parts
        # 3. Send to the AI provider
        # 4. Execute any tools requested by the AI
        # 5. Return the AI's response
        
        cls._log.info("Chat request", {
            "session_id": request.session_id,
            "provider": request.provider_id,
            "model": request.model_id,
            "mode": request.mode
        })
        
        # For now, return a simple response
        from .message import TextPart
        response_part = TextPart(text="This is a placeholder response. AI integration not yet implemented.")
        
        return ChatResponse(parts=[response_part])
    
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