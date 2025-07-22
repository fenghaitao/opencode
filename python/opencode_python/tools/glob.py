"""Glob pattern matching tool."""

import os
import glob
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .tool import Tool, ToolContext, ToolResult
from ..app import App


class GlobParams(BaseModel):
    """Parameters for Glob tool."""
    pattern: str = Field(description="The glob pattern to match files against")
    path: Optional[str] = Field(
        None,
        description="The directory to search in. If not specified, the current working directory will be used. IMPORTANT: Omit this field to use the default directory. DO NOT enter 'undefined' or 'null' - simply omit it for the default behavior. Must be a valid directory path if provided."
    )


class GlobTool(Tool):
    """Tool for finding files using glob patterns."""
    
    def __init__(self):
        super().__init__(
            tool_id="glob",
            description=self._load_description(),
            parameters=GlobParams
        )
    
    def _load_description(self) -> str:
        """Load description from glob.txt file."""
        try:
            import os
            current_dir = os.path.dirname(__file__)
            desc_path = os.path.join(current_dir, "..", "..", "..", "packages", "opencode", "src", "tool", "glob.txt")
            with open(desc_path, 'r') as f:
                return f.read()
        except:
            return "Find files using glob patterns."
    
    async def execute(self, args: GlobParams, ctx: ToolContext) -> ToolResult:
        """Execute the Glob tool."""
        app_info = App.info()
        search_path = args.path or app_info.path["cwd"]
        
        if not os.path.isabs(search_path):
            search_path = os.path.join(app_info.path["cwd"], search_path)
        
        search_path = os.path.abspath(search_path)
        
        limit = 100
        files = []
        truncated = False
        
        # Use glob to find matching files
        pattern_path = os.path.join(search_path, "**", args.pattern)
        matched_files = glob.glob(pattern_path, recursive=True)
        
        # Get file stats and sort by modification time
        file_stats = []
        for file_path in matched_files:
            if os.path.isfile(file_path):
                try:
                    mtime = os.path.getmtime(file_path)
                    file_stats.append({
                        "path": file_path,
                        "mtime": mtime
                    })
                except OSError:
                    continue
        
        # Sort by modification time (newest first)
        file_stats.sort(key=lambda x: x["mtime"], reverse=True)
        
        # Apply limit
        if len(file_stats) > limit:
            truncated = True
            file_stats = file_stats[:limit]
        
        files = [f["path"] for f in file_stats]
        
        # Build output
        output_lines = []
        if not files:
            output_lines.append("No files found")
        else:
            output_lines.extend(files)
            if truncated:
                output_lines.append("")
                output_lines.append("(Results are truncated. Consider using a more specific path or pattern.)")
        
        return ToolResult(
            title=os.path.relpath(search_path, app_info.path["root"]),
            metadata={
                "count": len(files),
                "truncated": truncated
            },
            output="\n".join(output_lines)
        )