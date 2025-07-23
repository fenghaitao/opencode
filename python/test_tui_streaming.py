#!/usr/bin/env python3
"""Debug script for TUI streaming issues."""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path so we can import opencode_python
sys.path.insert(0, str(Path(__file__).parent))

from opencode_python.session.session import Session, SessionChatRequest
from opencode_python.provider import ProviderManager, GitHubCopilotProvider
from opencode_python.app import App as OpenCodeApp


async def debug_tui_streaming():
    """Debug TUI streaming behavior."""
    print("=== TUI Streaming Debug ===")
    
    async def run_test(info=None):
        # Register providers
        ProviderManager.register(GitHubCopilotProvider())
        
        # Create test session
        session = await Session.create(mode="default")
        print(f"Session created: {session.id}")
        
        # Test message
        message = "Who are you?"
        print(f"Message: {message}")
        
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
                
                # Simulate TUI behavior
                current_content = ""
                chunk_count = 0
                
                print("Iterating through chunks...")
                async for chunk in streaming_response:
                    chunk_count += 1
                    chunk_type = chunk.get("type", "")
                    content = chunk.get("content", "")
                    
                    print(f"Chunk {chunk_count}: {chunk_type} - '{content}' (len={len(content)})")
                    
                    if chunk_type == "content":
                        current_content += content
                        print(f"  Accumulated: '{current_content}' (len={len(current_content)})")
                    elif chunk_type == "complete":
                        print(f"  Complete! Final content: '{current_content}'")
                        break
                    elif chunk_type == "error":
                        print(f"  Error: {content}")
                        break
                
                print(f"\nFinal streaming response content: '{streaming_response.content}'")
                print(f"Streaming completed successfully")
                return True
                
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        return await test_streaming()
    
    return await OpenCodeApp.provide(".", run_test)


if __name__ == "__main__":
    asyncio.run(debug_tui_streaming())