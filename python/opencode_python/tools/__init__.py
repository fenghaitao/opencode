"""Tool system for OpenCode Python."""

from .tool import Tool, ToolContext, ToolInfo, ToolResult
from .registry import ToolRegistry
from .bash import BashTool
from .edit import EditTool
from .glob import GlobTool
from .grep import GrepTool
from .ls import ListTool
from .lsp_diagnostics import LSPDiagnosticsTool
from .lsp_hover import LSPHoverTool
from .multiedit import MultiEditTool
from .patch import PatchTool
from .read import ReadTool
from .task import TaskTool
from .todo import TodoReadTool, TodoWriteTool
from .webfetch import WebFetchTool
from .write import WriteTool

__all__ = [
    "Tool",
    "ToolContext", 
    "ToolInfo",
    "ToolResult",
    "ToolRegistry",
    "BashTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    "ListTool",
    "LSPDiagnosticsTool",
    "LSPHoverTool",
    "MultiEditTool",
    "PatchTool",
    "ReadTool",
    "TaskTool",
    "TodoReadTool",
    "TodoWriteTool",
    "WebFetchTool",
    "WriteTool",
]