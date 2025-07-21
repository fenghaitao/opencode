# Development Guide

This guide covers development setup and architecture for OpenCode Python.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- pip or poetry for package management
- Git

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd opencode_python

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=opencode_python

# Run specific test file
pytest tests/test_tools.py

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check .

# Fix linting issues
ruff check --fix .

# Type checking
mypy .
```

## Architecture Overview

OpenCode Python follows a modular architecture similar to the original TypeScript version:

### Core Components

1. **App (`app.py`)**: Application context and lifecycle management
2. **Config (`config.py`)**: Configuration management with JSON persistence
3. **Session (`session/`)**: Chat session and message handling
4. **Tools (`tools/`)**: Individual tools for different operations
5. **Provider (`provider/`)**: AI model provider abstraction
6. **LSP (`lsp/`)**: Language Server Protocol integration
7. **CLI (`cli.py`)**: Command-line interface

### Key Design Patterns

- **Context Management**: Uses Python's `contextvars` for dependency injection
- **Async/Await**: Fully async architecture for better performance
- **Pydantic Models**: Type-safe data validation and serialization
- **Plugin Architecture**: Tools and providers are easily extensible

### Data Flow

1. CLI receives user input
2. App context is established
3. Session is created/retrieved
4. Message is processed through AI provider
5. Tools are executed as needed
6. Results are returned to user

## Adding New Components

### Creating a New Tool

```python
from pydantic import BaseModel, Field
from .tool import Tool, ToolContext, ToolResult

class MyToolParameters(BaseModel):
    param1: str = Field(description="Description of parameter")
    param2: int = Field(default=10, description="Optional parameter")

class MyTool(Tool):
    def __init__(self):
        super().__init__(
            tool_id="mytool",
            description="Description of what this tool does",
            parameters=MyToolParameters
        )
    
    async def execute(self, args: MyToolParameters, ctx: ToolContext) -> ToolResult:
        # Implement tool logic here
        return ToolResult(
            title="Tool execution result",
            metadata={"key": "value"},
            output="Tool output"
        )
```

### Adding a New Provider

```python
from .provider import Provider, ProviderInfo, ModelInfo, ChatRequest, ChatResponse

class MyProvider(Provider):
    def __init__(self):
        super().__init__("myprovider")
    
    async def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name="My Provider",
            description="Description of the provider",
            models=[
                ModelInfo(
                    id="model-1",
                    name="Model 1",
                    description="Model description",
                    context_length=4096,
                )
            ]
        )
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        # Implement API call to your provider
        pass
    
    async def is_authenticated(self) -> bool:
        # Check authentication status
        pass
    
    async def authenticate(self, **kwargs) -> bool:
        # Implement authentication
        pass
```

### Creating a New Mode

```python
from opencode_python.session import Mode, ModeInfo

# Create mode programmatically
mode = ModeInfo(
    name="mymode",
    description="Custom mode description",
    system_prompt="System prompt for the mode",
    tools=["bash", "read", "write"],
    temperature=0.7
)

await Mode.create(mode)
```

## Testing Guidelines

- Write tests for all new functionality
- Use `pytest` fixtures for common setup
- Mock external dependencies (API calls, file system when appropriate)
- Test both success and error cases
- Aim for >90% code coverage

### Test Structure

```python
import pytest
from opencode_python.tools import MyTool

@pytest.mark.asyncio
async def test_my_tool():
    tool = MyTool()
    # Test implementation
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Ensure all tests pass
6. Submit a pull request

### Commit Messages

Use conventional commit format:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `test:` for test additions/changes
- `refactor:` for code refactoring

## Performance Considerations

- Use async/await for I/O operations
- Implement proper error handling and timeouts
- Cache expensive operations when possible
- Use streaming for large responses
- Monitor memory usage for large files

## Security Notes

- Validate all user inputs
- Sanitize file paths to prevent directory traversal
- Use secure methods for storing API keys
- Implement proper permission checks for file operations
- Be cautious with code execution tools