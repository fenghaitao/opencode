#!/usr/bin/env python3
"""Test script to verify tools work in streaming mode."""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path so we can import opencode_python
sys.path.insert(0, str(Path(__file__).parent))

from opencode_python.session.session import Session, SessionChatRequest
from opencode_python.provider import ProviderManager, GitHubCopilotProvider
from opencode_python.app import App as OpenCodeApp
from opencode_python.tools import ToolRegistry


async def test_tools_streaming():
    """Test if tools work in streaming mode."""
    print("=== Tools Streaming Test ===")
    
    async def run_test(info=None):
        # Register providers
        ProviderManager.register(GitHubCopilotProvider())
        
        # Create test session
        session = await Session.create(mode="default")
        print(f"Session created: {session.id}")
        
        # Test message that should trigger git tools
        message = "What files have been changed in this git repository?"
        print(f"Message: {message}")
        
        # Check available tools
        available_tools = ToolRegistry.list_available("default")
        print(f"Available tools: {[t.name for t in available_tools]}")
        
        async def test_streaming():
            request = SessionChatRequest(
                session_id=session.id,
                provider_id="github-copilot",
                model_id="claude-3.5-sonnet",
                mode="default",
                message_content=message
            )
            
            print("Starting streaming...")
            
            try:
                streaming_response = await Session.chat_streaming(request)
                print("Streaming response created")
                
                # Check if tools were provided
                print(f"Final tool_calls: {streaming_response.tool_calls}")
                print(f"Final content: {streaming_response.content}")
                
                # Simulate streaming
                chunk_count = 0
                tool_chunks = []
                
                async for chunk in streaming_response:
                    chunk_count += 1
                    chunk_type = chunk.get("type", "")
                    content = chunk.get("content", "")
                    
                    print(f"Chunk {chunk_count}: {chunk_type}")
                    if chunk_type == "tool_calls":
                        tool_chunks.append(chunk)
                        print(f"  Tool calls: {chunk.get('tool_calls', [])}")
                    elif chunk_type == "content":
                        print(f"  Content: '{content}'")
                    elif chunk_type == "tool_start":
                        print(f"  Tool start: {content}")
                    elif chunk_type == "tool_result":
                        print(f"  Tool result: {content}")
                
                print(f"Total chunks: {chunk_count}")
                print(f"Tool chunks: {len(tool_chunks)}")
                
                return True
                
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        return await test_streaming()
    
    return await OpenCodeApp.provide(".", run_test)


if __name__ == "__main__":
    asyncio.run(test_tools_streaming())