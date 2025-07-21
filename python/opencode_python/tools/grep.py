"""Grep tool for searching text in files."""

import os
import re
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from ..app import App
from ..util.filesystem import Filesystem
from .tool import Tool, ToolContext, ToolResult


class GrepParameters(BaseModel):
    """Parameters for grep tool."""
    
    pattern: str = Field(description="The pattern to search for")
    file_pattern: str = Field(
        default="*",
        description="File pattern to search in (glob pattern)"
    )
    directory: Optional[str] = Field(
        default=None,
        description="Directory to search in (defaults to current directory)"
    )
    recursive: bool = Field(
        default=True,
        description="Search recursively in subdirectories"
    )
    case_sensitive: bool = Field(
        default=False,
        description="Case sensitive search"
    )
    regex: bool = Field(
        default=False,
        description="Treat pattern as regular expression"
    )
    max_results: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of results to return"
    )
    context_lines: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Number of context lines to show around matches"
    )


class GrepTool(Tool):
    """Tool for searching text in files."""
    
    def __init__(self):
        super().__init__(
            tool_id="grep",
            description="Search for text patterns in files",
            parameters=GrepParameters
        )
    
    async def execute(self, args: GrepParameters, ctx: ToolContext) -> ToolResult:
        """Search for text patterns in files."""
        app_info = App.info()
        
        # Determine search directory
        if args.directory:
            if not os.path.isabs(args.directory):
                search_dir = os.path.join(app_info.path["cwd"], args.directory)
            else:
                search_dir = args.directory
        else:
            search_dir = app_info.path["cwd"]
        
        search_dir = os.path.normpath(search_dir)
        
        if not os.path.exists(search_dir):
            raise FileNotFoundError(f"Directory not found: {search_dir}")
        
        if not os.path.isdir(search_dir):
            raise ValueError(f"Path is not a directory: {search_dir}")
        
        # Compile pattern
        flags = 0 if args.case_sensitive else re.IGNORECASE
        
        if args.regex:
            try:
                pattern = re.compile(args.pattern, flags)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        else:
            # Escape special regex characters for literal search
            escaped_pattern = re.escape(args.pattern)
            pattern = re.compile(escaped_pattern, flags)
        
        # Find files to search
        files_to_search = self._find_files(search_dir, args.file_pattern, args.recursive)
        
        # Search files
        results = []
        total_matches = 0
        
        for file_path in files_to_search:
            if total_matches >= args.max_results:
                break
            
            try:
                matches = self._search_file(file_path, pattern, args.context_lines)
                if matches:
                    results.extend(matches)
                    total_matches += len(matches)
            except Exception:
                # Skip files that can't be read
                continue
        
        # Limit results
        if len(results) > args.max_results:
            results = results[:args.max_results]
        
        # Format output
        if not results:
            output = f"No matches found for pattern: {args.pattern}"
        else:
            output = self._format_results(results, search_dir, app_info.path["root"])
        
        return ToolResult(
            title=f"Found {len(results)} matches",
            metadata={
                "pattern": args.pattern,
                "files_searched": len(files_to_search),
                "matches_found": len(results),
            },
            output=output
        )
    
    def _find_files(self, directory: str, file_pattern: str, recursive: bool) -> List[str]:
        """Find files matching the pattern."""
        files = []
        
        if recursive:
            files = Filesystem.find_files(file_pattern, directory)
        else:
            # Search only in the immediate directory
            try:
                for entry in os.listdir(directory):
                    entry_path = os.path.join(directory, entry)
                    if os.path.isfile(entry_path):
                        if self._matches_pattern(entry, file_pattern):
                            files.append(entry_path)
            except OSError:
                pass
        
        # Filter out binary files and large files
        text_files = []
        for file_path in files:
            if (Filesystem.is_text_file(file_path) and 
                not Filesystem.is_binary_file(file_path) and
                Filesystem.get_file_size(file_path) < 1024 * 1024):  # 1MB limit
                text_files.append(file_path)
        
        return text_files
    
    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches glob pattern."""
        import fnmatch
        return fnmatch.fnmatch(filename, pattern)
    
    def _search_file(self, file_path: str, pattern: re.Pattern, context_lines: int) -> List[dict]:
        """Search for pattern in a single file."""
        matches = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except Exception:
            return matches
        
        for line_num, line in enumerate(lines, 1):
            if pattern.search(line):
                # Get context lines
                start_line = max(0, line_num - 1 - context_lines)
                end_line = min(len(lines), line_num + context_lines)
                
                context = []
                for i in range(start_line, end_line):
                    prefix = ">" if i == line_num - 1 else " "
                    context.append(f"{prefix} {i + 1:4d}: {lines[i].rstrip()}")
                
                matches.append({
                    "file": file_path,
                    "line_number": line_num,
                    "line": line.rstrip(),
                    "context": context,
                })
        
        return matches
    
    def _format_results(self, results: List[dict], search_dir: str, root_dir: str) -> str:
        """Format search results for output."""
        output_lines = []
        current_file = None
        
        for result in results:
            file_path = result["file"]
            relative_path = Filesystem.get_relative_path(file_path, root_dir)
            
            if file_path != current_file:
                if current_file is not None:
                    output_lines.append("")  # Blank line between files
                output_lines.append(f"=== {relative_path} ===")
                current_file = file_path
            
            if result["context"]:
                output_lines.extend(result["context"])
            else:
                output_lines.append(f"> {result['line_number']:4d}: {result['line']}")
        
        return "\n".join(output_lines)