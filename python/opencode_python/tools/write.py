"""Write tool for creating/writing files."""

import os
from pathlib import Path

from pydantic import BaseModel, Field

from ..app import App
from ..util.filesystem import Filesystem
from .tool import Tool, ToolContext, ToolResult


class WriteParameters(BaseModel):
    """Parameters for write tool."""
    
    file_path: str = Field(description="The path to the file to write")
    content: str = Field(description="The content to write to the file")
    create_dirs: bool = Field(
        default=True,
        description="Create parent directories if they don't exist"
    )


class WriteTool(Tool):
    """Tool for writing file contents."""
    
    def __init__(self):
        super().__init__(
            tool_id="write",
            description="Write content to a file",
            parameters=WriteParameters
        )
    
    async def execute(self, args: WriteParameters, ctx: ToolContext) -> ToolResult:
        """Write content to a file."""
        app_info = App.info()
        
        # Resolve file path
        if not os.path.isabs(args.file_path):
            file_path = os.path.join(app_info.path["cwd"], args.file_path)
        else:
            file_path = args.file_path
        
        file_path = os.path.normpath(file_path)
        
        # Create parent directories if needed
        if args.create_dirs:
            parent_dir = os.path.dirname(file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
        
        # Check if file exists
        file_existed = os.path.exists(file_path)
        
        try:
            # Write content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(args.content)
            
            # Get file info
            file_size = len(args.content.encode('utf-8'))
            line_count = args.content.count('\n') + (1 if args.content and not args.content.endswith('\n') else 0)
            
            relative_path = Filesystem.get_relative_path(file_path, app_info.path["root"])
            
            action = "Updated" if file_existed else "Created"
            
            return ToolResult(
                title=f"{action} {relative_path}",
                metadata={
                    "file_path": file_path,
                    "file_size": file_size,
                    "line_count": line_count,
                    "action": action.lower(),
                },
                output=f"{action} file: {relative_path}\nSize: {file_size} bytes\nLines: {line_count}"
            )
            
        except Exception as e:
            return ToolResult(
                title=f"Error writing {args.file_path}",
                metadata={"error": str(e)},
                output=f"<error>\nFailed to write file: {e}\n</error>"
            )