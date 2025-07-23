#!/usr/bin/env python3
"""Test script for streaming functionality."""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import opencode_python
sys.path.insert(0, str(Path(__file__).parent))

from opencode_python.session.session import Session, SessionChatRequest
from opencode_python.provider import ProviderManager, OpenAIProvider, AnthropicProvider, GitHubCopilotProvider


async def test_streaming():
    """Test streaming functionality."""
    print("Testing streaming functionality...")
    
    # Register providers
    ProviderManager.register(OpenAIProvider())
    ProviderManager.register(AnthropicProvider())
    ProviderManager.register(GitHubCopilotProvider())
    
    # Create a test session request
    request = SessionChatRequest(
        session_id="test-session",
        provider_id="github_copilot",  # Use GitHub Copilot as it has streaming support
        model_id="gpt-4",
        mode="default",
        message_content="Hello! Please tell me a short joke."
    )
    
    print(f"Sending streaming request to {request.provider_id}...")
    
    try:
        # Test streaming
        streaming_response = await Session.chat_streaming(request)
        
        print("Streaming response created, starting iteration...")
        chunk_count = 0
        total_content = ""
        
        async for chunk in streaming_response:
            chunk_count += 1
            chunk_type = chunk.get("type", "")
            content = chunk.get("content", "")
            
            print(f"Chunk {chunk_count}: {chunk_type} - '{content}' (len={len(content)})")
            
            if chunk_type == "content":
                total_content += content
                print(f"  Accumulated: '{total_content}' (total len={len(total_content)})")
            elif chunk_type == "error":
                print(f"  Error: {content}")
                break
            elif chunk_type == "complete":
                usage = chunk.get("usage")
                print(f"  Complete! Usage: {usage}")
                break
        
        print(f"\nStreaming test completed:")
        print(f"  Total chunks: {chunk_count}")
        print(f"  Final content: '{total_content}' (len={len(total_content)})")
        print(f"  Session response content: '{streaming_response.content}' (len={len(streaming_response.content)})")
        print(f"  Is complete: {streaming_response.is_complete}")
        
        if total_content:
            print("✅ Streaming test PASSED - Content was received")
        else:
            print("❌ Streaming test FAILED - No content received")
            
    except Exception as e:
        print(f"❌ Streaming test FAILED with exception: {e}")
        import traceback
        traceback.print_exc()


async def test_non_streaming():
    """Test non-streaming functionality for comparison."""
    print("\nTesting non-streaming functionality...")
    
    # Create a test session request
    request = SessionChatRequest(
        session_id="test-session",
        provider_id="github_copilot",
        model_id="gpt-4",
        mode="default",
        message_content="Hello! Please tell me a short joke."
    )
    
    print(f"Sending non-streaming request to {request.provider_id}...")
    
    try:
        # Test non-streaming
        response = await Session.chat(request)
        
        print(f"Non-streaming response:")
        print(f"  Content: '{response.content}' (len={len(response.content)})")
        print(f"  Tool calls: {len(response.tool_calls)}")
        
        if response.content:
            print("✅ Non-streaming test PASSED - Content was received")
        else:
            print("❌ Non-streaming test FAILED - No content received")
            
    except Exception as e:
        print(f"❌ Non-streaming test FAILED with exception: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main test function."""
    print("OpenCode Python Streaming Test")
    print("=" * 50)
    
    # Test both streaming and non-streaming
    await test_streaming()
    await test_non_streaming()
    
    print("\nTest completed!")


if __name__ == "__main__":
    asyncio.run(main())
