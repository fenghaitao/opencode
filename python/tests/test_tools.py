"""Tests for tool system."""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from opencode_python.tools import BashTool, ReadTool, WriteTool, EditTool, GrepTool
from opencode_python.tools.tool import ToolContext


class MockToolContext(ToolContext):
    """Mock tool context for testing."""
    
    def __init__(self):
        super().__init__(
            session_id="test-session",
            message_id="test-message", 
            abort_event=asyncio.Event(),
            metadata_callback=lambda x: None
        )


@pytest.mark.asyncio
async def test_bash_tool():
    """Test bash tool execution."""
    tool = BashTool()
    ctx = MockToolContext()
    
    # Test simple command
    result = await tool.execute(
        tool.parameters(command="echo 'hello world'", description="Print hello world"),
        ctx
    )
    
    assert "hello world" in result.output
    assert result.metadata["exit_code"] == 0


@pytest.mark.asyncio
async def test_write_read_tools():
    """Test write and read tools."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Set up app context
        from opencode_python.app import App
        
        async def test_with_app():
            write_tool = WriteTool()
            read_tool = ReadTool()
            ctx = MockToolContext()
            
            test_file = os.path.join(temp_dir, "test.txt")
            test_content = "Hello, World!\nThis is a test file.\nLine 3"
            
            # Test write
            write_result = await write_tool.execute(
                write_tool.parameters(file_path=test_file, content=test_content),
                ctx
            )
            
            assert "Created" in write_result.title
            assert os.path.exists(test_file)
            
            # Test read
            read_result = await read_tool.execute(
                read_tool.parameters(file_path=test_file),
                ctx
            )
            
            assert test_content in read_result.output
            assert "00001|" in read_result.output  # Line numbers
        
        await App.provide(temp_dir, lambda _: test_with_app())


@pytest.mark.asyncio
async def test_edit_tool():
    """Test edit tool."""
    with tempfile.TemporaryDirectory() as temp_dir:
        from opencode_python.app import App
        
        async def test_with_app():
            write_tool = WriteTool()
            edit_tool = EditTool()
            ctx = MockToolContext()
            
            test_file = os.path.join(temp_dir, "test.py")
            original_content = "def hello():\n    print('Hello')\n    return 'world'"
            
            # Create file
            await write_tool.execute(
                write_tool.parameters(file_path=test_file, content=original_content),
                ctx
            )
            
            # Edit file
            edit_result = await edit_tool.execute(
                edit_tool.parameters(
                    file_path=test_file,
                    old_string="print('Hello')",
                    new_string="print('Hello, World!')"
                ),
                ctx
            )
            
            assert "test.py" in edit_result.title
            
            # Verify edit
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            assert "Hello, World!" in new_content
            assert "Hello'" not in new_content  # Old text should be gone
        
        await App.provide(temp_dir, lambda _: test_with_app())


@pytest.mark.asyncio
async def test_grep_tool():
    """Test grep tool."""
    with tempfile.TemporaryDirectory() as temp_dir:
        from opencode_python.app import App
        
        async def test_with_app():
            # Create test files
            test_files = {
                "file1.py": "def hello():\n    print('Hello World')\n    return True",
                "file2.js": "function hello() {\n    console.log('Hello World');\n    return true;\n}",
                "file3.txt": "This is a test file\nwith some content\nHello World here too"
            }
            
            for filename, content in test_files.items():
                with open(os.path.join(temp_dir, filename), 'w') as f:
                    f.write(content)
            
            grep_tool = GrepTool()
            ctx = MockToolContext()
            
            # Search for pattern
            result = await grep_tool.execute(
                grep_tool.parameters(
                    pattern="Hello World",
                    directory=temp_dir
                ),
                ctx
            )
            
            assert "3 matches" in result.title
            assert "file1.py" in result.output
            assert "file2.js" in result.output
            assert "file3.txt" in result.output
        
        await App.provide(temp_dir, lambda _: test_with_app())


if __name__ == "__main__":
    pytest.main([__file__])