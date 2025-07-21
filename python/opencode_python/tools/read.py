"""Read tool for reading file contents."""

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from ..app import App
from ..util.filesystem import Filesystem
from .tool import Tool, ToolContext, ToolResult

MAX_READ_SIZE = 250 * 1024  # 250KB
DEFAULT_READ_LIMIT = 2000
MAX_LINE_LENGTH = 2000


class ReadParameters(BaseModel):
    """Parameters for read tool."""
    
    file_path: str = Field(description="The path to the file to read")
    offset: Optional[int] = Field(
        default=None,
        ge=0,
        description="The line number to start reading from (0-based)"
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        description="The number of lines to read (defaults to 2000)"
    )


class ReadTool(Tool):
    """Tool for reading file contents."""
    
    def __init__(self):
        super().__init__(
            tool_id="read",
            description="Read the contents of a file",
            parameters=ReadParameters
        )
    
    async def execute(self, args: ReadParameters, ctx: ToolContext) -> ToolResult:
        """Read file contents."""
        app_info = App.info()
        
        # Resolve file path
        if not os.path.isabs(args.file_path):
            file_path = os.path.join(app_info.path["cwd"], args.file_path)
        else:
            file_path = args.file_path
        
        file_path = os.path.normpath(file_path)
        
        # Check if file exists
        if not os.path.exists(file_path):
            # Try to suggest similar files
            dir_path = os.path.dirname(file_path)
            base_name = os.path.basename(file_path)
            
            suggestions = []
            if os.path.exists(dir_path):
                try:
                    entries = os.listdir(dir_path)
                    suggestions = [
                        os.path.join(dir_path, entry)
                        for entry in entries
                        if (base_name.lower() in entry.lower() or 
                            entry.lower() in base_name.lower())
                    ][:3]
                except OSError:
                    pass
            
            error_msg = f"File not found: {file_path}"
            if suggestions:
                error_msg += f"\n\nDid you mean one of these?\n" + "\n".join(suggestions)
            
            raise FileNotFoundError(error_msg)
        
        # Check file size
        file_size = Filesystem.get_file_size(file_path)
        if file_size > MAX_READ_SIZE:
            raise ValueError(
                f"File is too large ({file_size} bytes). "
                f"Maximum size is {MAX_READ_SIZE} bytes"
            )
        
        # Check if it's an image file
        image_type = self._is_image_file(file_path)
        if image_type:
            raise ValueError(
                f"This is an image file of type: {image_type}\n"
                "Use a different tool to process images"
            )
        
        # Read file
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                content = f.read()
        
        lines = content.split('\n')
        
        # Apply offset and limit
        offset = args.offset or 0
        limit = args.limit or DEFAULT_READ_LIMIT
        
        selected_lines = lines[offset:offset + limit]
        
        # Truncate long lines
        truncated_lines = []
        for line in selected_lines:
            if len(line) > MAX_LINE_LENGTH:
                truncated_lines.append(line[:MAX_LINE_LENGTH] + "...")
            else:
                truncated_lines.append(line)
        
        # Format with line numbers
        formatted_lines = []
        for i, line in enumerate(truncated_lines):
            line_num = offset + i + 1
            formatted_lines.append(f"{line_num:5d}| {line}")
        
        # Create output
        output = "<file>\n" + "\n".join(formatted_lines)
        
        if len(lines) > offset + len(selected_lines):
            output += f"\n\n(File has more lines. Use 'offset' parameter to read beyond line {offset + len(selected_lines)})"
        
        output += "\n</file>"
        
        # Create preview (first 20 lines)
        preview = "\n".join(truncated_lines[:20])
        
        relative_path = Filesystem.get_relative_path(file_path, app_info.path["root"])
        
        return ToolResult(
            title=relative_path,
            metadata={"preview": preview},
            output=output
        )
    
    def _is_image_file(self, file_path: str) -> Optional[str]:
        """Check if file is an image and return the type."""
        ext = Path(file_path).suffix.lower()
        image_types = {
            '.jpg': 'JPEG',
            '.jpeg': 'JPEG', 
            '.png': 'PNG',
            '.gif': 'GIF',
            '.bmp': 'BMP',
            '.svg': 'SVG',
            '.webp': 'WebP',
        }
        return image_types.get(ext)