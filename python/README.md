# OpenCode Python

A Python port of the OpenCode AI coding agent, built for the terminal.

## Features

- 🤖 AI-powered coding assistance
- 🔧 Multiple tool integrations (bash, edit, read, grep, etc.)
- 🌐 Language Server Protocol (LSP) support
- 📝 Session management and chat history
- 🔌 Multiple AI provider support (OpenAI, Anthropic, etc.)
- 🎨 Rich terminal UI
- 🔄 Real-time file watching and diagnostics

## Installation

```bash
pip install opencode-python
```

Or for development:

```bash
git clone <repository>
cd opencode_python
pip install -e ".[dev]"
```

## Usage

```bash
# Start interactive session
opencode

# Run with a message
opencode run "Help me fix this bug"

# Continue last session
opencode run --continue

# Use specific model
opencode run --model anthropic/claude-3-sonnet "Refactor this code"

# Start server mode
opencode serve --port 8080
```

## Configuration

Configuration files are stored in platform-specific directories:
- Linux: `~/.config/opencode/`
- macOS: `~/Library/Application Support/opencode/`
- Windows: `%APPDATA%/opencode/`

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
ruff check --fix .

# Type checking
mypy .
```

## Architecture

The Python port maintains the same architecture as the original TypeScript version:

- **CLI**: Command-line interface with multiple commands
- **Tools**: Individual tools for different operations (bash, edit, read, etc.)
- **Session**: Chat session management and message handling
- **LSP**: Language Server Protocol integration
- **Provider**: AI model provider abstraction
- **Server**: HTTP API server for remote access

## License

MIT License - see LICENSE file for details.