"""LSP hover tool for getting symbol information."""

from pydantic import BaseModel, Field

from .tool import Tool, ToolContext, ToolResult
from ..lsp import LSPClient


class LSPHoverParams(BaseModel):
    """Parameters for LSP Hover tool."""
    filePath: str = Field(description="The file path to get hover information for")
    line: int = Field(description="The line number (0-based)")
    character: int = Field(description="The character position (0-based)")


class LSPHoverTool(Tool):
    """Tool for getting LSP hover information for symbols."""
    
    def __init__(self):
        super().__init__(
            tool_id="lsp-hover",
            description=self._load_description(),
            parameters=LSPHoverParams
        )
    
    def _load_description(self) -> str:
        """Load description from lsp-hover.txt file."""
        try:
            import os
            current_dir = os.path.dirname(__file__)
            desc_path = os.path.join(current_dir, "..", "..", "..", "packages", "opencode", "src", "tool", "lsp-hover.txt")
            with open(desc_path, 'r') as f:
                return f.read()
        except:
            return "Get hover information (documentation, type info) for symbols at specific positions."
    
    async def execute(self, args: LSPHoverParams, ctx: ToolContext) -> ToolResult:
        """Execute the LSP Hover tool."""
        try:
            lsp_client = LSPClient()
            
            hover_info = await lsp_client.get_hover(
                file_path=args.filePath,
                line=args.line,
                character=args.character
            )
            
            if not hover_info:
                return ToolResult(
                    title="No hover information",
                    metadata={
                        "filePath": args.filePath,
                        "line": args.line,
                        "character": args.character
                    },
                    output="No hover information available at this position."
                )
            
            # Extract hover content
            contents = hover_info.get('contents', [])
            if isinstance(contents, str):
                hover_text = contents
            elif isinstance(contents, list):
                hover_text = "\n".join([
                    item.get('value', str(item)) if isinstance(item, dict) else str(item)
                    for item in contents
                ])
            elif isinstance(contents, dict):
                hover_text = contents.get('value', str(contents))
            else:
                hover_text = str(contents)
            
            return ToolResult(
                title=f"Hover info at {args.filePath}:{args.line+1}:{args.character+1}",
                metadata={
                    "filePath": args.filePath,
                    "line": args.line,
                    "character": args.character,
                    "hover_info": hover_info
                },
                output=hover_text
            )
        
        except Exception as e:
            return ToolResult(
                title="LSP Hover (Error)",
                metadata={
                    "error": str(e),
                    "filePath": args.filePath,
                    "line": args.line,
                    "character": args.character
                },
                output=f"Error getting hover information: {str(e)}"
            )