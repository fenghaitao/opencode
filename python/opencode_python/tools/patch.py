"""Patch tool for applying unified diff patches to files."""

import os
import tempfile
import subprocess
from typing import Optional

from pydantic import BaseModel, Field

from .tool import Tool, ToolContext, ToolResult
from ..app import App


class PatchParams(BaseModel):
    """Parameters for Patch tool."""
    filePath: str = Field(description="The absolute path to the file to patch")
    patch: str = Field(description="The unified diff patch to apply")
    reverse: Optional[bool] = Field(False, description="Apply patch in reverse")


class PatchTool(Tool):
    """Tool for applying unified diff patches to files."""
    
    def __init__(self):
        super().__init__(
            tool_id="patch",
            description=self._load_description(),
            parameters=PatchParams
        )
    
    def _load_description(self) -> str:
        """Load description from patch.txt file."""
        try:
            import os
            current_dir = os.path.dirname(__file__)
            desc_path = os.path.join(current_dir, "..", "..", "..", "packages", "opencode", "src", "tool", "patch.txt")
            with open(desc_path, 'r') as f:
                return f.read()
        except:
            return "Apply unified diff patches to files."
    
    async def execute(self, args: PatchParams, ctx: ToolContext) -> ToolResult:
        """Execute the Patch tool."""
        app_info = App.info()
        
        # Resolve file path
        if not os.path.isabs(args.filePath):
            file_path = os.path.join(app_info.path["cwd"], args.filePath)
        else:
            file_path = args.filePath
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Create temporary patch file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as patch_file:
            patch_file.write(args.patch)
            patch_file_path = patch_file.name
        
        try:
            # Prepare patch command
            cmd = ['patch']
            if args.reverse:
                cmd.append('-R')
            cmd.extend(['-p0', file_path])
            
            # Apply patch
            with open(patch_file_path, 'r') as patch_input:
                result = subprocess.run(
                    cmd,
                    stdin=patch_input,
                    capture_output=True,
                    text=True,
                    cwd=app_info.path["cwd"]
                )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise Exception(f"Patch failed: {error_msg}")
            
            # Read the patched file to show result
            with open(file_path, 'r') as f:
                patched_content = f.read()
            
            return ToolResult(
                title=os.path.relpath(file_path, app_info.path["root"]),
                metadata={
                    "filePath": file_path,
                    "reverse": args.reverse,
                    "success": True
                },
                output=f"Patch applied successfully to {file_path}\n\n{result.stdout}"
            )
        
        finally:
            # Clean up temporary patch file
            try:
                os.unlink(patch_file_path)
            except OSError:
                pass