"""LSP diagnostics tool for getting language server diagnostics."""

from typing import Optional

from pydantic import BaseModel, Field

from .tool import Tool, ToolContext, ToolResult
from ..lsp import LSPClient


class LSPDiagnosticsParams(BaseModel):
    """Parameters for LSP Diagnostics tool."""
    filePath: Optional[str] = Field(
        None,
        description="Optional file path to get diagnostics for. If not provided, gets diagnostics for all files."
    )


class LSPDiagnosticsTool(Tool):
    """Tool for getting LSP diagnostics (errors, warnings, etc.)."""
    
    def __init__(self):
        super().__init__(
            tool_id="lsp-diagnostics",
            description=self._load_description(),
            parameters=LSPDiagnosticsParams
        )
    
    def _load_description(self) -> str:
        """Load description from lsp-diagnostics.txt file."""
        try:
            import os
            current_dir = os.path.dirname(__file__)
            desc_path = os.path.join(current_dir, "..", "..", "..", "packages", "opencode", "src", "tool", "lsp-diagnostics.txt")
            with open(desc_path, 'r') as f:
                return f.read()
        except:
            return "Get language server diagnostics (errors, warnings, hints) for files."
    
    async def execute(self, args: LSPDiagnosticsParams, ctx: ToolContext) -> ToolResult:
        """Execute the LSP Diagnostics tool."""
        try:
            lsp_client = LSPClient()
            
            if args.filePath:
                # Get diagnostics for specific file
                diagnostics = await lsp_client.get_diagnostics(args.filePath)
                file_diagnostics = {args.filePath: diagnostics}
            else:
                # Get diagnostics for all files
                file_diagnostics = await lsp_client.get_all_diagnostics()
            
            # Format output
            output_lines = []
            total_issues = 0
            
            for file_path, diagnostics in file_diagnostics.items():
                if not diagnostics:
                    continue
                
                output_lines.append(f"\n{file_path}:")
                for diagnostic in diagnostics:
                    severity = diagnostic.get('severity', 1)
                    severity_name = {1: 'ERROR', 2: 'WARNING', 3: 'INFO', 4: 'HINT'}.get(severity, 'UNKNOWN')
                    
                    line = diagnostic.get('range', {}).get('start', {}).get('line', 0) + 1
                    col = diagnostic.get('range', {}).get('start', {}).get('character', 0) + 1
                    message = diagnostic.get('message', 'No message')
                    
                    output_lines.append(f"  Line {line}:{col} [{severity_name}] {message}")
                    total_issues += 1
            
            if not output_lines:
                output = "No diagnostics found."
            else:
                output = f"Found {total_issues} diagnostic issues:\n" + "\n".join(output_lines)
            
            return ToolResult(
                title=f"LSP Diagnostics ({total_issues} issues)",
                metadata={
                    "total_issues": total_issues,
                    "files_with_issues": len([f for f, d in file_diagnostics.items() if d]),
                    "diagnostics": file_diagnostics
                },
                output=output
            )
        
        except Exception as e:
            return ToolResult(
                title="LSP Diagnostics (Error)",
                metadata={"error": str(e)},
                output=f"Error getting LSP diagnostics: {str(e)}"
            )