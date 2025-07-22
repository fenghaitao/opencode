"""Todo management tools for task tracking."""

import json
from typing import Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field

from .tool import Tool, ToolContext, ToolResult
from ..app import App


class TodoStatus(str, Enum):
    """Todo item status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TodoPriority(str, Enum):
    """Todo item priority."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TodoInfo(BaseModel):
    """Todo item information."""
    content: str = Field(min_length=1, description="Brief description of the task")
    status: TodoStatus = Field(description="Current status of the task")
    priority: TodoPriority = Field(description="Priority level of the task")
    id: str = Field(description="Unique identifier for the todo item")


class TodoWriteParams(BaseModel):
    """Parameters for TodoWrite tool."""
    todos: List[TodoInfo] = Field(description="The updated todo list")


class TodoReadParams(BaseModel):
    """Parameters for TodoRead tool (empty)."""
    pass


class TodoWriteTool(Tool):
    """Tool for writing/updating todo lists."""
    
    def __init__(self):
        super().__init__(
            tool_id="todowrite",
            description=self._load_description(),
            parameters=TodoWriteParams
        )
    
    def _load_description(self) -> str:
        """Load description from todowrite.txt file."""
        try:
            import os
            current_dir = os.path.dirname(__file__)
            desc_path = os.path.join(current_dir, "..", "..", "..", "packages", "opencode", "src", "tool", "todowrite.txt")
            with open(desc_path, 'r') as f:
                return f.read()
        except:
            return "Use this tool to create and manage a structured task list for your current coding session."
    
    async def execute(self, args: TodoWriteParams, ctx: ToolContext) -> ToolResult:
        """Execute the TodoWrite tool."""
        # Get or create todo state for this session
        state = App.get_state("todo-tool", lambda: {})
        state[ctx.session_id] = [todo.model_dump() for todo in args.todos]
        
        incomplete_count = len([todo for todo in args.todos if todo.status != TodoStatus.COMPLETED])
        
        return ToolResult(
            title=f"{incomplete_count} todos",
            output=json.dumps([todo.model_dump() for todo in args.todos], indent=2),
            metadata={
                "todos": [todo.model_dump() for todo in args.todos]
            }
        )


class TodoReadTool(Tool):
    """Tool for reading todo lists."""
    
    def __init__(self):
        super().__init__(
            tool_id="todoread",
            description=self._load_description(),
            parameters=TodoReadParams
        )
    
    def _load_description(self) -> str:
        """Load description from todoread.txt file."""
        try:
            import os
            current_dir = os.path.dirname(__file__)
            desc_path = os.path.join(current_dir, "..", "..", "..", "packages", "opencode", "src", "tool", "todoread.txt")
            with open(desc_path, 'r') as f:
                return f.read()
        except:
            return "Use this tool to read the current to-do list for the session."
    
    async def execute(self, args: TodoReadParams, ctx: ToolContext) -> ToolResult:
        """Execute the TodoRead tool."""
        # Get todo state for this session
        state = App.get_state("todo-tool", lambda: {})
        todos_data = state.get(ctx.session_id, [])
        todos = [TodoInfo(**todo) for todo in todos_data]
        
        incomplete_count = len([todo for todo in todos if todo.status != TodoStatus.COMPLETED])
        
        return ToolResult(
            title=f"{incomplete_count} todos",
            output=json.dumps([todo.model_dump() for todo in todos], indent=2),
            metadata={
                "todos": [todo.model_dump() for todo in todos]
            }
        )