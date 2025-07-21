"""Edit tool for modifying file contents."""

import os
from pathlib import Path
from typing import Generator, Optional

import diff_match_patch as dmp_module
from pydantic import BaseModel, Field

from ..app import App
from ..util.filesystem import Filesystem
from .tool import Tool, ToolContext, ToolResult


class EditParameters(BaseModel):
    """Parameters for edit tool."""
    
    file_path: str = Field(description="The absolute path to the file to modify")
    old_string: str = Field(description="The text to replace")
    new_string: str = Field(description="The text to replace it with (must be different from old_string)")
    replace_all: bool = Field(
        default=False,
        description="Replace all occurrences of old_string (default false)"
    )


class EditTool(Tool):
    """Tool for editing file contents."""
    
    def __init__(self):
        super().__init__(
            tool_id="edit",
            description="Edit a file by replacing text",
            parameters=EditParameters
        )
    
    async def execute(self, args: EditParameters, ctx: ToolContext) -> ToolResult:
        """Edit file contents."""
        if not args.file_path:
            raise ValueError("file_path is required")
        
        if args.old_string == args.new_string:
            raise ValueError("old_string and new_string must be different")
        
        app_info = App.info()
        
        # Resolve file path
        if not os.path.isabs(args.file_path):
            file_path = os.path.join(app_info.path["cwd"], args.file_path)
        else:
            file_path = args.file_path
        
        file_path = os.path.normpath(file_path)
        
        # Handle empty old_string (create new file)
        if args.old_string == "":
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(args.new_string)
            
            relative_path = Filesystem.get_relative_path(file_path, app_info.path["root"])
            return ToolResult(
                title=relative_path,
                metadata={"diff": f"Created new file with {len(args.new_string)} characters"},
                output=f"Created new file: {relative_path}"
            )
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {file_path} not found")
        
        if os.path.isdir(file_path):
            raise ValueError(f"Path is a directory, not a file: {file_path}")
        
        # Read current content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content_old = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                content_old = f.read()
        
        # Perform replacement
        try:
            content_new = self._replace_text(content_old, args.old_string, args.new_string, args.replace_all)
        except ValueError as e:
            raise ValueError(str(e))
        
        # Write new content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content_new)
        
        # Generate diff
        diff = self._create_diff(file_path, content_old, content_new)
        
        relative_path = Filesystem.get_relative_path(file_path, app_info.path["root"])
        
        return ToolResult(
            title=relative_path,
            metadata={"diff": diff},
            output=f"Edited file: {relative_path}\n\n{diff}"
        )
    
    def _replace_text(self, content: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        """Replace text in content using various strategies."""
        if old_string == new_string:
            raise ValueError("old_string and new_string must be different")
        
        # Try different replacement strategies
        replacers = [
            self._simple_replacer,
            self._line_trimmed_replacer,
            self._whitespace_normalized_replacer,
            self._indentation_flexible_replacer,
        ]
        
        for replacer in replacers:
            for search_text in replacer(content, old_string):
                index = content.find(search_text)
                if index == -1:
                    continue
                
                if replace_all:
                    return content.replace(search_text, new_string)
                
                # Check for multiple occurrences
                last_index = content.rfind(search_text)
                if index != last_index:
                    continue
                
                # Replace single occurrence
                return content[:index] + new_string + content[index + len(search_text):]
        
        raise ValueError("old_string not found in content or was found multiple times")
    
    def _simple_replacer(self, content: str, find: str) -> Generator[str, None, None]:
        """Simple exact match replacer."""
        yield find
    
    def _line_trimmed_replacer(self, content: str, find: str) -> Generator[str, None, None]:
        """Replacer that matches lines with trimmed whitespace."""
        original_lines = content.split('\n')
        search_lines = find.split('\n')
        
        if search_lines and search_lines[-1] == "":
            search_lines.pop()
        
        for i in range(len(original_lines) - len(search_lines) + 1):
            matches = True
            
            for j in range(len(search_lines)):
                if original_lines[i + j].strip() != search_lines[j].strip():
                    matches = False
                    break
            
            if matches:
                # Calculate the exact substring
                start_index = sum(len(line) + 1 for line in original_lines[:i])
                end_index = start_index + sum(len(original_lines[i + k]) + 1 for k in range(len(search_lines)))
                yield content[start_index:end_index - 1]  # -1 to remove last newline
    
    def _whitespace_normalized_replacer(self, content: str, find: str) -> Generator[str, None, None]:
        """Replacer that normalizes whitespace."""
        def normalize_whitespace(text: str) -> str:
            return ' '.join(text.split())
        
        normalized_find = normalize_whitespace(find)
        lines = content.split('\n')
        
        for line in lines:
            if normalize_whitespace(line) == normalized_find:
                yield line
    
    def _indentation_flexible_replacer(self, content: str, find: str) -> Generator[str, None, None]:
        """Replacer that ignores leading whitespace differences."""
        def remove_indentation(text: str) -> str:
            lines = text.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            if not non_empty_lines:
                return text
            
            min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)
            return '\n'.join(line[min_indent:] if line.strip() else line for line in lines)
        
        normalized_find = remove_indentation(find)
        content_lines = content.split('\n')
        find_lines = find.split('\n')
        
        for i in range(len(content_lines) - len(find_lines) + 1):
            block = '\n'.join(content_lines[i:i + len(find_lines)])
            if remove_indentation(block) == normalized_find:
                yield block
    
    def _create_diff(self, file_path: str, old_content: str, new_content: str) -> str:
        """Create a unified diff between old and new content."""
        dmp = dmp_module.diff_match_patch()
        diffs = dmp.diff_main(old_content, new_content)
        dmp.diff_cleanupSemantic(diffs)
        
        # Convert to unified diff format
        lines = []
        lines.append(f"--- {file_path}")
        lines.append(f"+++ {file_path}")
        
        old_line_num = 1
        new_line_num = 1
        
        for op, text in diffs:
            if op == dmp.DIFF_EQUAL:
                for line in text.split('\n')[:-1]:  # Exclude last empty line
                    lines.append(f" {line}")
                    old_line_num += 1
                    new_line_num += 1
            elif op == dmp.DIFF_DELETE:
                for line in text.split('\n')[:-1]:
                    lines.append(f"-{line}")
                    old_line_num += 1
            elif op == dmp.DIFF_INSERT:
                for line in text.split('\n')[:-1]:
                    lines.append(f"+{line}")
                    new_line_num += 1
        
        return '\n'.join(lines)