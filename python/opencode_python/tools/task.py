"""Task tool for launching sub-agents with specific tool access."""

import json
from typing import Dict, Optional

from pydantic import BaseModel, Field

from .tool import Tool, ToolContext, ToolResult


class TaskParams(BaseModel):
    """Parameters for Task tool."""
    instruction: str = Field(description="The instruction or task for the sub-agent to complete")
    tools: Optional[Dict[str, bool]] = Field(
        None,
        description="Override tool availability for the sub-agent. If not specified, uses default tool set."
    )


class TaskTool(Tool):
    """Tool for launching sub-agents with specific capabilities."""
    
    def __init__(self):
        super().__init__(
            tool_id="task",
            description=self._load_description(),
            parameters=TaskParams
        )
    
    def _load_description(self) -> str:
        """Load description from task.txt file."""
        try:
            import os
            current_dir = os.path.dirname(__file__)
            desc_path = os.path.join(current_dir, "..", "..", "..", "packages", "opencode", "src", "tool", "task.txt")
            with open(desc_path, 'r') as f:
                return f.read()
        except:
            return "Launch a new agent that has access to specific tools for completing focused tasks."
    
    async def execute(self, args: TaskParams, ctx: ToolContext) -> ToolResult:
        """Execute the Task tool."""
        # Default tool configuration for sub-agents
        default_tools = {
            "bash": True,
            "glob": True,
            "grep": True,
            "list": True,
            "read": True,
            "edit": True,
            "multiedit": True,
            "write": True,
            "webfetch": True,
            "todoread": False,  # Disabled by default for sub-agents
            "todowrite": False,  # Disabled by default for sub-agents
        }
        
        # Override with user-specified tools
        if args.tools:
            default_tools.update(args.tools)
        
        # For now, this is a placeholder implementation
        # In a full implementation, this would spawn a new agent session
        # with the specified tools and instruction
        
        return ToolResult(
            title="Task Agent",
            metadata={
                "instruction": args.instruction,
                "tools": default_tools,
                "session_id": ctx.session_id
            },
            output=f"Task agent would be launched with instruction: {args.instruction}\n\nAvailable tools: {json.dumps(default_tools, indent=2)}\n\n[Note: This is a placeholder implementation. Full task agent spawning would require additional infrastructure.]"
        )