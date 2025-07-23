#!/usr/bin/env python3
"""Isolated test for streaming functionality without dependencies."""

import asyncio
from typing import Dict, Any, Optional


class StreamingSessionResponse:
    """Streaming response from session chat - isolated copy for testing."""
    
    def __init__(self, session_id: str, message_id: str):
        self.session_id = session_id
        self.message_id = message_id
        self.content = ""
        self.tool_calls = []
        self.usage = None
        self.is_complete = False
        
        # Use asyncio.Queue for proper async coordination
        self._chunk_queue = asyncio.Queue()
        self._processing_started = asyncio.Event()
        self._processing_complete = asyncio.Event()
        self._error = None
    
    def __aiter__(self):
        """Async iterator for streaming chunks."""
        return self
    
    async def __anext__(self):
        """Get next chunk."""
        # Wait for processing to start
        await self._processing_started.wait()
        
        try:
            # Use timeout to avoid hanging indefinitely
            chunk = await asyncio.wait_for(self._chunk_queue.get(), timeout=30.0)
            
            # Check for sentinel value indicating completion
            if chunk is None:
                raise StopAsyncIteration
                
            # Check for error
            if isinstance(chunk, Exception):
                raise chunk
                
            return chunk
            
        except asyncio.TimeoutError:
            if self.is_complete:
                raise StopAsyncIteration
            raise RuntimeError("Streaming timeout - no chunks received")
    
    def add_chunk(self, chunk_type: str, content: str = "", **kwargs):
        """Add a streaming chunk."""
        chunk = {
            "type": chunk_type,
            "content": content,
            **kwargs
        }
        
        # Add to queue in a thread-safe way
        try:
            self._chunk_queue.put_nowait(chunk)
        except asyncio.QueueFull:
            # If queue is full, this is a programming error
            raise RuntimeError("Streaming chunk queue is full")
        
        if chunk_type == "content":
            self.content += content
    
    def complete(self, usage: Optional[Dict[str, Any]] = None):
        """Mark the response as complete."""
        self.usage = usage
        self.is_complete = True
        self.add_chunk("complete")
        # Add sentinel value to signal completion
        try:
            self._chunk_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass  # Ignore if queue is full at completion
        self._processing_complete.set()
    
    def set_error(self, error: Exception):
        """Set an error for the streaming response."""
        self._error = error
        try:
            self._chunk_queue.put_nowait(error)
        except asyncio.QueueFull:
            pass  # Ignore if queue is full
        self._processing_complete.set()
    
    def start_processing(self):
        """Signal that processing has started."""
        self._processing_started.set()


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


async def test_race_condition():
    """Test that there's no race condition between starting iteration and processing."""
    print("\nTesting race condition handling...")
    
    response = StreamingSessionResponse("test-session", "test-message")
    
    # Start iteration before processing starts
    async def iterate():
        chunks = []
        async for chunk in response:
            chunks.append(chunk)
        return chunks
    
    # Start iteration task
    iteration_task = asyncio.create_task(iterate())
    
    # Wait a bit, then start processing
    await asyncio.sleep(0.1)
    response.start_processing()
    
    # Add chunks
    response.add_chunk("content", "Test")
    response.complete()
    
    # Wait for iteration to complete
    chunks = await iteration_task
    
    print(f"Received {len(chunks)} chunks")
    if len(chunks) == 2:  # content + complete
        print("✅ Race condition handled correctly")
    else:
        print(f"❌ Expected 2 chunks, got {len(chunks)}")


async def main():
    """Main test function."""
    print("OpenCode Python Streaming Response Test (Isolated)")
    print("=" * 60)
    
    await test_streaming_response()
    await test_streaming_error()
    await test_race_condition()
    
    print("\nTest completed!")


if __name__ == "__main__":
    asyncio.run(main())
