"""Message and part definitions for chat sessions."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class PartType(str, Enum):
    """Types of message parts."""
    TEXT = "text"
    TOOL = "tool"


class ToolState(str, Enum):
    """Tool execution states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class TextPart(BaseModel):
    """Text message part."""
    
    type: Literal[PartType.TEXT] = PartType.TEXT
    text: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ToolPart(BaseModel):
    """Tool execution message part."""
    
    type: Literal[PartType.TOOL] = PartType.TOOL
    tool: str
    args: Dict[str, Any]
    state: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @property
    def status(self) -> ToolState:
        """Get tool execution status."""
        return ToolState(self.state.get("status", ToolState.PENDING))
    
    @property
    def title(self) -> Optional[str]:
        """Get tool execution title."""
        return self.state.get("title")
    
    @property
    def output(self) -> Optional[str]:
        """Get tool execution output."""
        return self.state.get("output")
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Get tool execution metadata."""
        return self.state.get("metadata", {})


MessagePart = Union[TextPart, ToolPart]


class Message(BaseModel):
    """Chat message containing multiple parts."""
    
    id: str
    session_id: str
    role: Literal["user", "assistant"] = "user"
    parts: List[MessagePart] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def add_text(self, text: str) -> TextPart:
        """Add a text part to the message."""
        part = TextPart(text=text)
        self.parts.append(part)
        return part
    
    def add_tool(self, tool: str, args: Dict[str, Any]) -> ToolPart:
        """Add a tool part to the message."""
        part = ToolPart(tool=tool, args=args)
        self.parts.append(part)
        return part
    
    def get_text_parts(self) -> List[TextPart]:
        """Get all text parts from the message."""
        return [part for part in self.parts if isinstance(part, TextPart)]
    
    def get_tool_parts(self) -> List[ToolPart]:
        """Get all tool parts from the message."""
        return [part for part in self.parts if isinstance(part, ToolPart)]
    
    def get_text_content(self) -> str:
        """Get concatenated text content from all text parts."""
        return "\n".join(part.text for part in self.get_text_parts())