#!/usr/bin/env python3
"""
Test script for GitHub Copilot provider.
"""

import asyncio
import sys
from pathlib import Path

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent))

from opencode_python.app import App
from opencode_python.provider import ProviderManager, GitHubCopilotProvider
from opencode_python.auth import Auth
from opencode_python.util.log import Log


async def test_github_copilot():
    """Test GitHub Copilot provider."""
    print("🤖 Testing GitHub Copilot Provider")
    print("=" * 50)
    
    async def run_test():
        # Register GitHub Copilot provider
        ProviderManager.register(GitHubCopilotProvider())
        
        # Get the provider
        provider = ProviderManager.get("github-copilot")
        if not provider:
            print("❌ GitHub Copilot provider not found")
            return
        
        # Get provider info
        info = await provider.get_info()
        print(f"✅ Provider: {info.name}")
        print(f"📋 Description: {info.description}")
        print(f"🔗 Auth URL: {info.auth_url}")
        print(f"📋 Available models: {len(info.models)}")
        
        for model in info.models:
            tools_support = "✓" if model.supports_tools else "✗"
            print(f"   - {model.name} ({model.id}) [Tools: {tools_support}]")
        
        # Check authentication
        print(f"\n🔑 Checking authentication...")
        auth_info = await Auth.get("github-copilot")
        
        if not auth_info:
            print("❌ No GitHub Copilot credentials found")
            print("Run: opencode auth login")
            print("Then select GitHub Copilot and follow the device flow")
            return
        
        print(f"✅ Found credentials (type: {auth_info.type})")
        
        # Test authentication
        is_auth = await provider.is_authenticated()
        if not is_auth:
            print("❌ Authentication failed")
            print("Your GitHub Copilot token may have expired")
            print("Run: opencode auth login")
            return
        
        print("✅ Authentication successful!")
        
        # Test a simple chat request
        print("\n🧪 Testing chat functionality...")
        
        try:
            from opencode_python.provider.provider import ChatRequest, ChatMessage
            
            request = ChatRequest(
                messages=[
                    ChatMessage(role="user", content="Hello! Can you help me write a simple Python function that calculates the factorial of a number?")
                ],
                model="gpt-4o-mini",  # Use the mini model for testing
                max_tokens=200
            )
            
            print("💬 Sending request to GitHub Copilot...")
            response = await provider.chat(request)
            
            print("✅ Response received!")
            print(f"📝 Content: {response.content[:300]}...")
            if response.usage:
                print(f"📊 Tokens used: {response.usage}")
            
            print("\n" + "=" * 50)
            print("🎉 GitHub Copilot test completed successfully!")
            print("\nYou can now use:")
            print("  opencode run --model github-copilot/gpt-4o 'Help me code'")
            print("  opencode run --model github-copilot/o1-preview 'Complex reasoning task'")
            
        except Exception as e:
            print(f"❌ Chat test failed: {e}")
            print("This might be due to:")
            print("1. Expired GitHub Copilot subscription")
            print("2. Invalid or expired tokens")
            print("3. Network connectivity issues")
    
    await App.provide(".", lambda _: run_test())


if __name__ == "__main__":
    asyncio.run(test_github_copilot())