"""Base tool definition and context."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Protocol

from pydantic import BaseModel


class ToolContext:
    """Context provided to tool execution."""
    
    def __init__(
        self,
        session_id: str,
        message_id: str,
        abort_event: asyncio.Event,
        metadata_callback: Callable[[Dict[str, Any]], None]
    ):
        self.session_id = session_id
        self.message_id = message_id
        self.abort_event = abort_event
        self._metadata_callback = metadata_callback
    
    def metadata(self, title: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Update tool metadata."""
        data = {}
        if title:
            data["title"] = title
        if metadata:
            data["metadata"] = metadata
        self._metadata_callback(data)
    
    @property
    def is_aborted(self) -> bool:
        """Check if execution should be aborted."""
        return self.abort_event.is_set()


class ToolResult(BaseModel):
    """Result from tool execution."""
    
    title: str
    metadata: Dict[str, Any]
    output: str


class ToolInfo(Protocol):
    """Tool information protocol."""
    
    id: str
    description: str
    parameters: type[BaseModel]
    
    async def execute(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        """Execute the tool with given arguments."""
        ...


class Tool(ABC):
    """Base class for tools."""
    
    def __init__(self, tool_id: str, description: str, parameters: type[BaseModel]):
        self.id = tool_id
        self.description = description
        self.parameters = parameters
    
    @abstractmethod
    async def execute(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        """Execute the tool with given arguments."""
        pass
    
    @classmethod
    def define(
        cls,
        tool_id: str,
        description: str,
        parameters: type[BaseModel],
        execute_func: Callable[[BaseModel, ToolContext], Any]
    ) -> "Tool":
        """Define a tool with a function."""
        
        class FunctionTool(Tool):
            async def execute(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
                result = execute_func(args, ctx)
                if asyncio.iscoroutine(result):
                    result = await result
                return result
        
        return FunctionTool(tool_id, description, parameters)