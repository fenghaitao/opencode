"""Tool registry and execution framework."""

import asyncio
import json
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from .tool import Tool, ToolContext, ToolResult
from .bash import BashTool
from .edit import EditTool
from .glob import GlobTool
from .grep import GrepTool
from .ls import ListTool
from .lsp_diagnostics import LSPDiagnosticsTool
from .lsp_hover import LSPHoverTool
from .multiedit import MultiEditTool
from .patch import PatchTool
from .read import ReadTool
from .task import TaskTool
from .todo import TodoReadTool, TodoWriteTool
from .webfetch import WebFetchTool
from .write import WriteTool


class ToolRegistry:
    """Registry for managing and executing tools."""
    
    _tools: Dict[str, Tool] = {}
    
    @classmethod
    def register_default_tools(cls):
        """Register all default OpenCode tools."""
        tools = [
            BashTool(),
            EditTool(),
            GlobTool(),
            GrepTool(),
            ListTool(),
            LSPDiagnosticsTool(),
            LSPHoverTool(),
            MultiEditTool(),
            PatchTool(),
            ReadTool(),
            TaskTool(),
            TodoReadTool(),
            TodoWriteTool(),
            WebFetchTool(),
            WriteTool(),
        ]
        
        for tool in tools:
            cls._tools[tool.id] = tool
    
    @classmethod
    def register(cls, tool: Tool):
        """Register a tool."""
        cls._tools[tool.id] = tool
    
    @classmethod
    def get(cls, tool_id: str) -> Optional[Tool]:
        """Get a tool by ID."""
        return cls._tools.get(tool_id)
    
    @classmethod
    def list_available(cls, enabled_tools: List[str]) -> List[Tool]:
        """Get list of available tools based on enabled list."""
        return [cls._tools[tool_id] for tool_id in enabled_tools if tool_id in cls._tools]
    
    @classmethod
    def to_openai_format(cls, tools: List[Tool]) -> List[Dict[str, Any]]:
        """Convert tools to OpenAI function calling format."""
        result = []
        for tool in tools:
            tool_spec = {
                "type": "function",
                "function": {
                    "name": tool.id,
                    "description": tool.description,
                    "parameters": cls._get_tool_parameters(tool)
                }
            }
            result.append(tool_spec)
        return result
    
    @classmethod
    def _get_tool_parameters(cls, tool: Tool) -> Dict[str, Any]:
        """Convert tool parameters to JSON schema format."""
        # This is a simplified version - in a full implementation,
        # you'd convert the Pydantic model to JSON schema
        if hasattr(tool, 'parameters') and tool.parameters:
            try:
                # Try to get schema from Pydantic model
                if hasattr(tool.parameters, 'model_json_schema'):
                    return tool.parameters.model_json_schema()
                elif hasattr(tool.parameters, 'schema'):
                    return tool.parameters.schema()
            except Exception:
                pass
        
        # Fallback to basic schema
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    @classmethod
    async def execute_tool(
        cls,
        tool_id: str,
        arguments: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Execute a tool with given arguments and context."""
        tool = cls.get(tool_id)
        if not tool:
            raise ValueError(f"Tool '{tool_id}' not found")
        
        # Parse arguments into tool's parameter model
        try:
            if tool.parameters:
                args = tool.parameters(**arguments)
            else:
                args = arguments
        except Exception as e:
            raise ValueError(f"Invalid arguments for tool '{tool_id}': {str(e)}")
        
        # Execute the tool
        try:
            result = await tool.execute(args, context)
            return result
        except Exception as e:
            # Return error as ToolResult
            return ToolResult(
                title=f"Tool Error: {tool_id}",
                metadata={"error": str(e)},
                output=f"Error executing {tool_id}: {str(e)}"
            )


# Initialize default tools
ToolRegistry.register_default_tools()