"""List directory contents tool."""

import os
import glob
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from .tool import Tool, ToolContext, ToolResult
from ..app import App


IGNORE_PATTERNS = [
    "node_modules/",
    "__pycache__/",
    ".git/",
    "dist/",
    "build/",
    "target/",
    "vendor/",
    "bin/",
    "obj/",
    ".idea/",
    ".vscode/",
    ".zig-cache/",
    "zig-out",
    ".coverage",
    "coverage/",
    "vendor/",
    "tmp/",
    "temp/",
    ".cache/",
    "cache/",
    "logs/",
    ".venv/",
    "venv/",
    "env/",
]

LIMIT = 100


class ListParams(BaseModel):
    """Parameters for List tool."""
    path: Optional[str] = Field(
        None, 
        description="The absolute path to the directory to list (must be absolute, not relative)"
    )
    ignore: Optional[List[str]] = Field(
        None,
        description="List of glob patterns to ignore"
    )


class ListTool(Tool):
    """Tool for listing directory contents."""
    
    def __init__(self):
        super().__init__(
            tool_id="list",
            description=self._load_description(),
            parameters=ListParams
        )
    
    def _load_description(self) -> str:
        """Load description from ls.txt file."""
        try:
            import os
            current_dir = os.path.dirname(__file__)
            desc_path = os.path.join(current_dir, "..", "..", "..", "packages", "opencode", "src", "tool", "ls.txt")
            with open(desc_path, 'r') as f:
                return f.read()
        except:
            return "List directory contents with optional filtering."
    
    async def execute(self, args: ListParams, ctx: ToolContext) -> ToolResult:
        """Execute the List tool."""
        app_info = App.info()
        search_path = Path(app_info.path["cwd"]) / (args.path or ".")
        search_path = search_path.resolve()
        
        files = []
        
        # Walk directory tree
        for root, dirs, filenames in os.walk(search_path):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if not any(
                d.startswith(pattern.rstrip('/')) for pattern in IGNORE_PATTERNS
            )]
            
            for filename in filenames:
                rel_path = os.path.relpath(os.path.join(root, filename), search_path)
                
                # Check ignore patterns
                if any(pattern.rstrip('/') in rel_path for pattern in IGNORE_PATTERNS):
                    continue
                
                # Check custom ignore patterns
                if args.ignore:
                    if any(Path(rel_path).match(pattern) for pattern in args.ignore):
                        continue
                
                files.append(rel_path)
                if len(files) >= LIMIT:
                    break
            
            if len(files) >= LIMIT:
                break
        
        # Build directory structure
        dirs_set = set()
        files_by_dir = {}
        
        for file in files:
            dir_path = os.path.dirname(file)
            if dir_path == "":
                dir_path = "."
            
            # Add all parent directories
            parts = dir_path.split(os.sep) if dir_path != "." else []
            for i in range(len(parts) + 1):
                dir_part = "." if i == 0 else os.sep.join(parts[:i])
                dirs_set.add(dir_part)
            
            # Add file to its directory
            if dir_path not in files_by_dir:
                files_by_dir[dir_path] = []
            files_by_dir[dir_path].append(os.path.basename(file))
        
        def render_dir(dir_path: str, depth: int) -> str:
            """Render directory tree."""
            indent = "  " * depth
            output = ""
            
            if depth > 0:
                output += f"{indent}{os.path.basename(dir_path)}/\n"
            
            child_indent = "  " * (depth + 1)
            children = sorted([
                d for d in dirs_set 
                if os.path.dirname(d) == dir_path and d != dir_path
            ])
            
            # Render subdirectories first
            for child in children:
                output += render_dir(child, depth + 1)
            
            # Render files
            dir_files = sorted(files_by_dir.get(dir_path, []))
            for file in dir_files:
                output += f"{child_indent}{file}\n"
            
            return output
        
        output = f"{search_path}/\n" + render_dir(".", 0)
        
        return ToolResult(
            title=os.path.relpath(str(search_path), app_info.path["root"]),
            metadata={
                "count": len(files),
                "truncated": len(files) >= LIMIT
            },
            output=output
        )