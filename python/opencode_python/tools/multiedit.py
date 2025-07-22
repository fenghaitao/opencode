"""Multi-edit tool for performing multiple edits on a single file."""

import os
from typing import List

from pydantic import BaseModel, Field

from .tool import Tool, ToolContext, ToolResult
from .edit import EditTool, EditParameters
from ..app import App


class MultiEditParams(BaseModel):
    """Parameters for MultiEdit tool."""
    filePath: str = Field(description="The absolute path to the file to modify")
    edits: List[EditParameters] = Field(description="Array of edit operations to perform sequentially on the file")


class MultiEditTool(Tool):
    """Tool for performing multiple edits on a single file."""
    
    def __init__(self):
        super().__init__(
            tool_id="multiedit",
            description=self._load_description(),
            parameters=MultiEditParams
        )
        self.edit_tool = EditTool()
    
    def _load_description(self) -> str:
        """Load description from multiedit.txt file."""
        try:
            import os
            current_dir = os.path.dirname(__file__)
            desc_path = os.path.join(current_dir, "..", "..", "..", "packages", "opencode", "src", "tool", "multiedit.txt")
            with open(desc_path, 'r') as f:
                return f.read()
        except:
            return "Perform multiple edit operations sequentially on a single file."
    
    async def execute(self, args: MultiEditParams, ctx: ToolContext) -> ToolResult:
        """Execute the MultiEdit tool."""
        results = []
        
        for edit in args.edits:
            # Create edit parameters for each edit
            edit_args = EditParameters(
                filePath=args.filePath,
                oldString=edit.oldString,
                newString=edit.newString,
                replaceAll=edit.replaceAll if hasattr(edit, 'replaceAll') else False
            )
            
            result = await self.edit_tool.execute(edit_args, ctx)
            results.append(result)
        
        app_info = App.info()
        
        return ToolResult(
            title=os.path.relpath(args.filePath, app_info.path["root"]),
            metadata={
                "results": [r.metadata for r in results]
            },
            output=results[-1].output if results else ""
        )