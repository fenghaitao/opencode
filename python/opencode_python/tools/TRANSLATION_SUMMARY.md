# TypeScript to Python Tools Translation Summary

This document summarizes the translation of all OpenCode tools from TypeScript to Python.

## Completed Tools

### Core File Operations
- ✅ **ReadTool** (`read.py`) - Read file contents with line numbering and range support
- ✅ **WriteTool** (`write.py`) - Write content to files with permission checks
- ✅ **EditTool** (`edit.py`) - Edit files using string replacement with diff generation
- ✅ **MultiEditTool** (`multiedit.py`) - Perform multiple edits on a single file sequentially

### Directory and File Discovery
- ✅ **ListTool** (`ls.py`) - List directory contents with tree structure
- ✅ **GlobTool** (`glob.py`) - Find files using glob patterns
- ✅ **GrepTool** (`grep.py`) - Search file contents using regex patterns

### Task Management
- ✅ **TodoWriteTool** (`todo.py`) - Create and manage structured task lists
- ✅ **TodoReadTool** (`todo.py`) - Read current todo lists for sessions

### System Operations
- ✅ **BashTool** (`bash.py`) - Execute bash commands with timeout support

### Language Server Protocol (LSP)
- ✅ **LSPDiagnosticsTool** (`lsp_diagnostics.py`) - Get language server diagnostics
- ✅ **LSPHoverTool** (`lsp_hover.py`) - Get hover information for symbols

### Advanced Operations
- ✅ **PatchTool** (`patch.py`) - Apply unified diff patches to files
- ✅ **WebFetchTool** (`webfetch.py`) - Fetch content from web URLs
- ✅ **TaskTool** (`task.py`) - Launch sub-agents with specific tool access

## Key Translation Features

### 1. Parameter Consistency
- All tools use `filePath` parameter (matching TypeScript convention)
- Consistent parameter naming across all tools
- Proper Pydantic validation with Field descriptions

### 2. Error Handling
- File existence checks with helpful suggestions
- Image file detection and appropriate error messages
- Proper exception handling with meaningful error messages

### 3. Output Formatting
- Consistent output formatting matching TypeScript tools
- Line numbering for file content (5-digit padding)
- Proper metadata structure for tool results

### 4. App Integration
- Integration with App.info() for path resolution
- Relative path calculation for titles
- Session-scoped state management for todos

### 5. Description Loading
- Each tool attempts to load descriptions from original .txt files
- Fallback descriptions when .txt files are not available
- Maintains compatibility with existing prompt system

## Tool-Specific Features

### ReadTool
- Image file detection and rejection
- Line length truncation (2000 chars max)
- File size limits (250KB max)
- Unicode handling with fallback encoding
- File suggestion on not found errors

### TodoTools
- Session-scoped todo storage
- Status tracking (pending, in_progress, completed, cancelled)
- Priority levels (high, medium, low)
- JSON output formatting

### LSP Tools
- Integration with LSP client system
- Proper error handling for LSP failures
- Formatted diagnostic output with severity levels

### WebFetchTool
- HTTP/HTTPS URL validation
- Timeout support
- Content type detection
- Binary content handling

### MultiEditTool
- Sequential edit processing
- Result aggregation
- Error propagation from individual edits

## Usage Example

```python
from opencode_python.tools import ReadTool, TodoWriteTool, ToolContext

# Create tool instances
read_tool = ReadTool()
todo_tool = TodoWriteTool()

# Create context
ctx = ToolContext(
    session_id="session_123",
    message_id="msg_456", 
    abort_event=asyncio.Event(),
    metadata_callback=lambda x: None
)

# Use tools
result = await read_tool.execute(
    ReadParameters(filePath="./example.py"),
    ctx
)
```

## Integration Points

1. **App State Management** - Tools integrate with App.state() for persistent data
2. **Permission System** - Write operations use Permission.ask() for user consent
3. **LSP Integration** - LSP tools connect to language server clients
4. **File Time Tracking** - File operations update FileTime for session tracking
5. **Bus Events** - File modifications publish events via Bus system

All tools maintain full compatibility with the TypeScript implementation while leveraging Python's strengths for async operations and type safety.