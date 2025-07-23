#!/usr/bin/env python3
"""Test script to verify tools and prompts work in streaming mode."""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path so we can import opencode_python
sys.path.insert(0, str(Path(__file__).parent))

from opencode_python.session.session import Session, SessionChatRequest
from opencode_python.provider import ProviderManager, GitHubCopilotProvider
from opencode_python.app import App as OpenCodeApp
from opencode_python.tools import ToolRegistry
from opencode_python.session.mode import Mode


async def test_complete_streaming():
    """Test complete streaming with tools and system prompts."""
    print("=== Complete Streaming Test (Tools + Prompts) ===")
    
    async def run_test(info=None):
        # Register providers
        ProviderManager.register(GitHubCopilotProvider())
        
        # Check mode configuration
        mode = await Mode.get('default')
        print(f"Mode: {mode.name}")
        print(f"Mode tools: {mode.tools}")
        
        # Check available tools
        available_tools = ToolRegistry.list_available(mode.tools)
        print(f"Available tools: {[t.__class__.__name__ for t in available_tools]}")
        
        # Create test session
        session = await Session.create(mode="default")
        print(f"Session created: {session.id}")
        
        # Test message that should trigger tools
        message = "List the files in the current directory"
        print(f"Message: {message}")
        
        async def test_streaming():
            request = SessionChatRequest(
                session_id=session.id,
                provider_id="github-copilot",
                model_id="claude-3.5-sonnet",
                mode="default",
                message_content=message
            )
            
            print("Starting streaming with tools...")
            
            try:
                streaming_response = await Session.chat_streaming(request)
                
                # Check what was in the request
                print("Streaming response created")
                
                # Simulate streaming to see what happens
                chunk_count = 0
                tool_calls_seen = []
                content_seen = []
                
                async for chunk in streaming_response:
                    chunk_count += 1
                    chunk_type = chunk.get("type", "")
                    
                    if chunk_type == "content":
                        content = chunk.get("content", "")
                        content_seen.append(content)
                        print(f"CONTENT: '{content}'")
                    elif chunk_type == "tool_calls":
                        tool_calls = chunk.get("tool_calls", [])
                        tool_calls_seen.extend(tool_calls)
                        print(f"TOOLS: {tool_calls}")
                    elif chunk_type == "tool_start":
                        tool_start = chunk.get("content", "")
                        print(f"TOOL START: {tool_start}")
                    elif chunk_type == "tool_result":
                        tool_result = chunk.get("content", "")
                        print(f"TOOL RESULT: {tool_result}")
                    elif chunk_type == "status":
                        status = chunk.get("content", "")
                        print(f"STATUS: {status}")
                    elif chunk_type == "complete":
                        usage = chunk.get("usage")
                        print(f"COMPLETE: usage={usage}")
                        break
                
                print(f"\nFinal results:")
                print(f"Total chunks: {chunk_count}")
                print(f"Tool calls: {len(tool_calls_seen)}")
                print(f"Tool calls details: {tool_calls_seen}")
                print(f"Final content: '{''.join(content_seen)}'")
                print(f"Streaming tools enabled: {len(available_tools) > 0}")
                
                return True
                
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        return await test_streaming()
    
    return await OpenCodeApp.provide(".", run_test)


if __name__ == "__main__":
    asyncio.run(test_complete_streaming())