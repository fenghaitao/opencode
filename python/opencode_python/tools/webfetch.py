"""Web fetch tool for retrieving content from URLs."""

import asyncio
import aiohttp
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from .tool import Tool, ToolContext, ToolResult


class WebFetchParams(BaseModel):
    """Parameters for WebFetch tool."""
    url: str = Field(description="The URL to fetch content from")
    timeout: Optional[int] = Field(30, description="Request timeout in seconds")


class WebFetchTool(Tool):
    """Tool for fetching content from web URLs."""
    
    def __init__(self):
        super().__init__(
            tool_id="webfetch",
            description=self._load_description(),
            parameters=WebFetchParams
        )
    
    def _load_description(self) -> str:
        """Load description from webfetch.txt file."""
        try:
            import os
            current_dir = os.path.dirname(__file__)
            desc_path = os.path.join(current_dir, "..", "..", "..", "packages", "opencode", "src", "tool", "webfetch.txt")
            with open(desc_path, 'r') as f:
                return f.read()
        except:
            return "Fetch content from web URLs."
    
    async def execute(self, args: WebFetchParams, ctx: ToolContext) -> ToolResult:
        """Execute the WebFetch tool."""
        # Validate URL
        parsed = urlparse(args.url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {args.url}")
        
        if parsed.scheme not in ['http', 'https']:
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
        
        timeout = aiohttp.ClientTimeout(total=args.timeout)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(args.url) as response:
                    if response.status >= 400:
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=f"HTTP {response.status}: {response.reason}"
                        )
                    
                    content_type = response.headers.get('content-type', '').lower()
                    
                    # Read content
                    if 'text/' in content_type or 'application/json' in content_type or 'application/xml' in content_type:
                        content = await response.text()
                    else:
                        # For binary content, provide basic info
                        content_length = response.headers.get('content-length', 'unknown')
                        content = f"Binary content ({content_type}, {content_length} bytes)"
                    
                    return ToolResult(
                        title=f"GET {args.url}",
                        metadata={
                            "url": args.url,
                            "status": response.status,
                            "content_type": content_type,
                            "content_length": len(content) if isinstance(content, str) else content_length
                        },
                        output=content
                    )
        
        except asyncio.TimeoutError:
            raise Exception(f"Request timeout after {args.timeout} seconds")
        except aiohttp.ClientError as e:
            raise Exception(f"Request failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")