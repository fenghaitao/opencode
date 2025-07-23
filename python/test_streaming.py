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
    
    # Providers will be auto-registered by Session class
    
    # Create a test session request
    request = SessionChatRequest(
        session_id="test-session",
        provider_id="github-copilot",  # Use GitHub Copilot (note the hyphen)
        model_id="claude-3.5-sonnet",
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
            return True
        else:
            print("❌ Streaming test FAILED - No content received")
            return False
            
    except Exception as e:
        print(f"❌ Streaming test FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_non_streaming():
    """Test non-streaming functionality for comparison."""
    print("\nTesting non-streaming functionality...")
    
    # Create a test session request
    request = SessionChatRequest(
        session_id="test-session",
        provider_id="github-copilot",  # Use GitHub Copilot (note the hyphen)
        model_id="claude-3.5-sonnet",
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
            return True
        else:
            print("❌ Non-streaming test FAILED - No content received")
            return False
            
    except Exception as e:
        print(f"❌ Non-streaming test FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    print("OpenCode Python Streaming Test")
    print("=" * 50)
    
    # Import App here to avoid circular imports
    from opencode_python.app import App as OpenCodeApp
    
    async def run_tests():
        # Test both streaming and non-streaming
        streaming_success = await test_streaming()
        non_streaming_success = await test_non_streaming()
        
        return streaming_success and non_streaming_success
    
    # Run tests within app context
    try:
        success = await OpenCodeApp.provide(".", lambda _: run_tests())
        
        print("\nTest completed!")
        
        if success:
            print("🎉 All tests PASSED!")
            return 0
        else:
            print("❌ Some tests FAILED!")
            return 1
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
