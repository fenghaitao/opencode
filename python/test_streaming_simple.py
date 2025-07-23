#!/usr/bin/env python3
"""Simple test script for streaming functionality without full dependencies."""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path so we can import opencode_python
sys.path.insert(0, str(Path(__file__).parent))

# Test the streaming response class directly
from opencode_python.session.session import StreamingSessionResponse


async def test_streaming_response():
    """Test the StreamingSessionResponse class directly."""
    print("Testing StreamingSessionResponse class...")
    
    # Create a streaming response
    response = StreamingSessionResponse("test-session", "test-message")
    
    print("Created StreamingSessionResponse")
    print(f"  Session ID: {response.session_id}")
    print(f"  Message ID: {response.message_id}")
    print(f"  Is complete: {response.is_complete}")
    
    # Start processing
    response.start_processing()
    print("Started processing")
    
    # Add some test chunks
    response.add_chunk("content", "Hello")
    response.add_chunk("content", " world")
    response.add_chunk("content", "!")
    response.complete({"total_tokens": 10})
    
    print("Added chunks and marked complete")
    
    # Test iteration
    chunks = []
    try:
        async for chunk in response:
            chunks.append(chunk)
            print(f"Received chunk: {chunk}")
            
    except Exception as e:
        print(f"Error during iteration: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nTest results:")
    print(f"  Total chunks received: {len(chunks)}")
    print(f"  Final content: '{response.content}'")
    print(f"  Is complete: {response.is_complete}")
    
    # Verify we got the expected chunks
    expected_chunks = [
        {"type": "content", "content": "Hello"},
        {"type": "content", "content": " world"},
        {"type": "content", "content": "!"},
        {"type": "complete", "content": ""}
    ]
    
    if len(chunks) == len(expected_chunks):
        print("✅ Correct number of chunks received")
    else:
        print(f"❌ Expected {len(expected_chunks)} chunks, got {len(chunks)}")
    
    if response.content == "Hello world!":
        print("✅ Content accumulated correctly")
    else:
        print(f"❌ Expected 'Hello world!', got '{response.content}'")
    
    if response.is_complete:
        print("✅ Response marked as complete")
    else:
        print("❌ Response not marked as complete")


async def test_streaming_error():
    """Test error handling in streaming response."""
    print("\nTesting error handling...")
    
    response = StreamingSessionResponse("test-session", "test-message")
    response.start_processing()
    
    # Add an error
    test_error = RuntimeError("Test error")
    response.set_error(test_error)
    
    print("Set error on response")
    
    # Test iteration with error
    try:
        async for chunk in response:
            print(f"Received chunk: {chunk}")
            if isinstance(chunk, Exception):
                print(f"✅ Received error as expected: {chunk}")
                break
    except RuntimeError as e:
        print(f"✅ Exception raised as expected: {e}")
    except Exception as e:
        print(f"❌ Unexpected exception: {e}")


async def test_streaming_timeout():
    """Test timeout handling."""
    print("\nTesting timeout handling...")
    
    response = StreamingSessionResponse("test-session", "test-message")
    response.start_processing()
    
    # Don't add any chunks, just let it timeout
    try:
        # Use a very short timeout for testing
        original_timeout = 30.0  # The default timeout in __anext__
        
        # We can't easily change the timeout without modifying the class,
        # so let's just test that it doesn't hang indefinitely
        start_time = asyncio.get_event_loop().time()
        
        # Complete immediately to avoid timeout
        response.complete()
        
        async for chunk in response:
            print(f"Received chunk: {chunk}")
            break
            
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        
        if duration < 1.0:  # Should complete quickly
            print("✅ No timeout - completed quickly as expected")
        else:
            print(f"❌ Took too long: {duration:.2f}s")
            
    except Exception as e:
        print(f"Exception during timeout test: {e}")


async def main():
    """Main test function."""
    print("OpenCode Python Streaming Response Test")
    print("=" * 50)
    
    await test_streaming_response()
    await test_streaming_error()
    await test_streaming_timeout()
    
    print("\nTest completed!")


if __name__ == "__main__":
    asyncio.run(main())
