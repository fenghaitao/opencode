#!/usr/bin/env python3
"""
Example usage of OpenCode Python.

This script demonstrates how to use the core components of OpenCode Python
to build an AI coding assistant.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the package to the path for this example
sys.path.insert(0, str(Path(__file__).parent))

from opencode_python.app import App
from opencode_python.config import Config
from opencode_python.session import Session, Mode
from opencode_python.tools import BashTool, ReadTool, WriteTool, EditTool, GrepTool
from opencode_python.provider import ProviderManager, OpenAIProvider, AnthropicProvider
from opencode_python.util.log import Log


async def setup_providers():
    """Set up AI providers."""
    print("Setting up AI providers...")
    
    # Register providers
    ProviderManager.register(OpenAIProvider())
    ProviderManager.register(AnthropicProvider())
    
    # Check authentication
    for provider in ProviderManager.list():
        is_auth = await provider.is_authenticated()
        print(f"  {provider.id}: {'✓' if is_auth else '✗'} {'Authenticated' if is_auth else 'Not authenticated'}")


async def demo_tools():
    """Demonstrate tool usage."""
    print("\n=== Tool Demonstration ===")
    
    # Create a mock tool context
    from opencode_python.tools.tool import ToolContext
    import asyncio
    
    class DemoContext(ToolContext):
        def __init__(self):
            super().__init__(
                session_id="demo-session",
                message_id="demo-message",
                abort_event=asyncio.Event(),
                metadata_callback=lambda x: print(f"  Metadata: {x}")
            )
    
    ctx = DemoContext()
    
    # Demo bash tool
    print("\n1. Bash Tool - List current directory:")
    bash_tool = BashTool()
    result = await bash_tool.execute(
        bash_tool.parameters(command="ls -la", description="List directory contents"),
        ctx
    )
    print(f"  Exit code: {result.metadata['exit_code']}")
    print(f"  Output preview: {result.output[:200]}...")
    
    # Demo write tool
    print("\n2. Write Tool - Create a test file:")
    write_tool = WriteTool()
    test_content = """# Test Python File
def hello_world():
    print("Hello from OpenCode Python!")
    return "success"

if __name__ == "__main__":
    result = hello_world()
    print(f"Result: {result}")
"""
    
    result = await write_tool.execute(
        write_tool.parameters(file_path="demo_test.py", content=test_content),
        ctx
    )
    print(f"  {result.title}")
    print(f"  File size: {result.metadata['file_size']} bytes")
    
    # Demo read tool
    print("\n3. Read Tool - Read the test file:")
    read_tool = ReadTool()
    result = await read_tool.execute(
        read_tool.parameters(file_path="demo_test.py"),
        ctx
    )
    print(f"  {result.title}")
    print(f"  Preview: {result.metadata['preview'][:100]}...")
    
    # Demo edit tool
    print("\n4. Edit Tool - Modify the test file:")
    edit_tool = EditTool()
    result = await edit_tool.execute(
        edit_tool.parameters(
            file_path="demo_test.py",
            old_string='print("Hello from OpenCode Python!")',
            new_string='print("Hello from OpenCode Python - Modified!")'
        ),
        ctx
    )
    print(f"  {result.title}")
    print(f"  Changes made successfully")
    
    # Demo grep tool
    print("\n5. Grep Tool - Search for 'hello' in Python files:")
    grep_tool = GrepTool()
    result = await grep_tool.execute(
        grep_tool.parameters(
            pattern="hello",
            file_pattern="*.py",
            case_sensitive=False
        ),
        ctx
    )
    print(f"  {result.title}")
    print(f"  Found {result.metadata['matches_found']} matches")
    
    # Cleanup
    try:
        os.remove("demo_test.py")
        print("\n  Cleaned up demo file")
    except:
        pass


async def demo_session_management():
    """Demonstrate session management."""
    print("\n=== Session Management ===")
    
    # List available modes
    print("\n1. Available modes:")
    modes = await Mode.list()
    for mode in modes:
        print(f"  - {mode.name}: {mode.description}")
    
    # Create a new session
    print("\n2. Creating a new session:")
    session = await Session.create(mode="default")
    print(f"  Session ID: {session.id}")
    print(f"  Mode: {session.mode}")
    print(f"  Created: {session.created}")
    
    # List sessions
    print("\n3. Listing sessions:")
    count = 0
    async for s in Session.list():
        print(f"  - {s.id[:8]}... ({s.mode}) - {s.message_count} messages")
        count += 1
        if count >= 3:  # Limit output
            break


async def demo_config():
    """Demonstrate configuration management."""
    print("\n=== Configuration Management ===")
    
    # Get current config
    config = await Config.get()
    print(f"\nCurrent configuration:")
    print(f"  Log level: {config.log_level}")
    print(f"  Auto share: {config.autoshare}")
    print(f"  Default provider: {config.default_provider}")
    print(f"  Default model: {config.default_model}")
    
    # Update config
    print(f"\nUpdating configuration...")
    await Config.update({
        "log_level": "INFO",
        "autoshare": False,
        "default_provider": "openai"
    })
    print("  Configuration updated")


async def main():
    """Main demo function."""
    print("🤖 OpenCode Python - Core Functionality Demo")
    print("=" * 50)
    
    # Initialize logging
    await Log.init(print_logs=True)
    
    async def run_demo():
        try:
            await setup_providers()
            await demo_config()
            await demo_session_management()
            await demo_tools()
            
            print("\n" + "=" * 50)
            print("✅ Demo completed successfully!")
            print("\nNext steps:")
            print("1. Set up API keys for OpenAI/Anthropic")
            print("2. Install LSP servers for your languages")
            print("3. Try the CLI: python -m opencode_python.cli --help")
            print("4. Extend with custom tools and modes")
            
        except Exception as e:
            print(f"\n❌ Demo failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Run within app context
    await App.provide(cwd=os.getcwd(), callback=lambda _: run_demo())


if __name__ == "__main__":
    asyncio.run(main())