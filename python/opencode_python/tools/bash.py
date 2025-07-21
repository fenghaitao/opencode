"""Bash tool for executing shell commands."""

import asyncio
import subprocess
from typing import Optional

from pydantic import BaseModel, Field

from ..app import App
from .tool import Tool, ToolContext, ToolResult

MAX_OUTPUT_LENGTH = 30000
DEFAULT_TIMEOUT = 60  # seconds
MAX_TIMEOUT = 600  # 10 minutes


class BashParameters(BaseModel):
    """Parameters for bash tool."""
    
    command: str = Field(description="The command to execute")
    timeout: Optional[int] = Field(
        default=None,
        ge=0,
        le=MAX_TIMEOUT,
        description="Optional timeout in seconds"
    )
    description: str = Field(
        description=(
            "Clear, concise description of what this command does in 5-10 words. "
            "Examples:\n"
            "Input: ls\n"
            "Output: Lists files in current directory\n\n"
            "Input: git status\n"
            "Output: Shows working tree status\n\n"
            "Input: npm install\n"
            "Output: Installs package dependencies\n\n"
            "Input: mkdir foo\n"
            "Output: Creates directory 'foo'"
        )
    )


class BashTool(Tool):
    """Tool for executing bash commands."""
    
    def __init__(self):
        super().__init__(
            tool_id="bash",
            description="Execute bash commands in the terminal",
            parameters=BashParameters
        )
    
    async def execute(self, args: BashParameters, ctx: ToolContext) -> ToolResult:
        """Execute a bash command."""
        timeout = min(args.timeout or DEFAULT_TIMEOUT, MAX_TIMEOUT)
        
        app_info = App.info()
        cwd = app_info.path["cwd"]
        
        try:
            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                args.command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=MAX_OUTPUT_LENGTH
            )
            
            # Wait for completion with timeout
            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise TimeoutError(f"Command timed out after {timeout} seconds")
            
            stdout = stdout_data.decode('utf-8', errors='replace') if stdout_data else ""
            stderr = stderr_data.decode('utf-8', errors='replace') if stderr_data else ""
            exit_code = process.returncode or 0
            
            # Truncate output if too long
            if len(stdout) > MAX_OUTPUT_LENGTH:
                stdout = stdout[:MAX_OUTPUT_LENGTH] + "\n... (output truncated)"
            if len(stderr) > MAX_OUTPUT_LENGTH:
                stderr = stderr[:MAX_OUTPUT_LENGTH] + "\n... (output truncated)"
            
            output_parts = [
                "<stdout>",
                stdout,
                "</stdout>",
                "<stderr>", 
                stderr,
                "</stderr>"
            ]
            
            return ToolResult(
                title=args.command,
                metadata={
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": exit_code,
                    "description": args.description,
                },
                output="\n".join(output_parts)
            )
            
        except Exception as e:
            return ToolResult(
                title=f"Error: {args.command}",
                metadata={
                    "error": str(e),
                    "description": args.description,
                },
                output=f"<error>\nFailed to execute command: {e}\n</error>"
            )