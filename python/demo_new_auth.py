#!/usr/bin/env python3
"""
Demo script showing the new GitHub Copilot authentication features.
This demonstrates the improved expire and refresh functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent))

from opencode_python.app import App
from opencode_python.auth import GitHubCopilotAuthManager, GitHubCopilotAuth
from opencode_python.auth import Auth


async def demo_auth_features():
    """Demonstrate the new authentication features."""
    print("🚀 GitHub Copilot Authentication Demo")
    print("=" * 50)
    
    async def run_demo():
        print("📋 Available features:")
        print("1. ✅ Device flow authorization (matches auth.ts)")
        print("2. ✅ Automatic token refresh")
        print("3. ✅ Token expiry checking")
        print("4. ✅ Proper error handling")
        print("5. ✅ Detailed logging")
        print()
        
        # Check current authentication status
        print("🔍 Checking current authentication status...")
        is_auth = await GitHubCopilotAuthManager.is_authenticated()
        print(f"Authentication status: {'✅ Authenticated' if is_auth else '❌ Not authenticated'}")
        
        if not is_auth:
            print("\n⚠️  No authentication found. Run this to authenticate:")
            print("   python -c \"from opencode_python.auth import GitHubCopilotAuthManager; import asyncio; asyncio.run(demo_device_flow())\"")
            return
        
        # Get current auth info
        auth_info = await Auth.get("github-copilot")
        if auth_info:
            import time
            current_time = int(time.time() * 1000)
            if auth_info.expires:
                expires_in = (auth_info.expires - current_time) // 1000
                print(f"🕐 Current token expires in: {expires_in} seconds")
                
                if expires_in < 300:  # Less than 5 minutes
                    print("⚠️  Token expires soon, will demonstrate refresh...")
                else:
                    print("✅ Token is still valid")
            else:
                print("⚠️  No expiry information (old token format)")
        
        # Test token retrieval (will auto-refresh if needed)
        print("\n🔑 Testing token retrieval...")
        token = await GitHubCopilotAuthManager.get_access_token()
        if token:
            print(f"✅ Got valid token (length: {len(token)})")
        else:
            print("❌ Failed to get token")
            return
        
        # Test forced refresh
        print("\n🔄 Testing forced token refresh...")
        new_token = await GitHubCopilotAuthManager.get_access_token(force_refresh=True)
        if new_token:
            print(f"✅ Forced refresh successful (length: {len(new_token)})")
            if new_token != token:
                print("🆕 Got a new token!")
            else:
                print("🔄 Same token returned (normal if recently refreshed)")
        else:
            print("❌ Forced refresh failed")
        
        # Show final auth info
        print("\n📊 Final authentication info:")
        final_auth = await Auth.get("github-copilot")
        if final_auth:
            import time
            current_time = int(time.time() * 1000)
            expires_in = (final_auth.expires - current_time) // 1000 if final_auth.expires else 0
            print(f"   Refresh token: {final_auth.refresh[:20]}...")
            print(f"   Access token: {final_auth.access[:20]}...")
            print(f"   Expires in: {expires_in} seconds")
        
        print("\n" + "=" * 50)
        print("🎉 Demo completed! Key improvements:")
        print("✅ Automatic token refresh when expired")
        print("✅ Proper expiry time handling (milliseconds)")
        print("✅ Force refresh capability")
        print("✅ Better error handling and logging")
        print("✅ Matches auth.ts TypeScript implementation")
    
    await App.provide(".", lambda _: run_demo())


async def demo_device_flow():
    """Demonstrate the device flow authentication."""
    print("🔐 GitHub Copilot Device Flow Demo")
    print("=" * 40)
    
    async def run_flow():
        try:
            # Start device flow
            print("1️⃣ Starting device authorization flow...")
            auth_result = await GitHubCopilotAuth.authorize()
            
            print(f"✅ Device flow started!")
            print(f"🔗 Go to: {auth_result.verification}")
            print(f"🔑 Enter code: {auth_result.user}")
            print(f"⏰ Code expires in: {auth_result.expiry} seconds")
            print(f"🔄 Will poll every: {auth_result.interval} seconds")
            
            print("\n2️⃣ Waiting for authorization...")
            print("   (Complete the authorization in your browser)")
            
            # Poll for completion
            import time
            start_time = time.time()
            while time.time() - start_time < auth_result.expiry:
                await asyncio.sleep(auth_result.interval)
                
                result = await GitHubCopilotAuth.poll(auth_result.device)
                
                if result.status == "success":
                    print("✅ Authorization successful!")
                    print("🔑 GitHub OAuth token received and stored")
                    
                    # Test getting Copilot token
                    print("\n3️⃣ Getting Copilot API token...")
                    access_result = await GitHubCopilotAuth.access(result.refresh)
                    if access_result:
                        print("✅ Copilot API token obtained!")
                        print(f"⏰ Token expires at: {access_result.expires}")
                        
                        # Store the complete auth info
                        from opencode_python.auth import OAuthInfo
                        complete_auth = OAuthInfo(
                            refresh=access_result.refresh,
                            access=access_result.access,
                            expires=access_result.expires
                        )
                        await Auth.set("github-copilot", complete_auth)
                        print("💾 Complete authentication stored!")
                        
                        print("\n🎉 Device flow completed successfully!")
                        return
                    else:
                        print("❌ Failed to get Copilot token")
                        return
                        
                elif result.status == "failed":
                    print("❌ Authorization failed")
                    return
                else:
                    print("⏳ Still waiting for authorization...")
            
            print("⏰ Authorization timed out")
            
        except Exception as e:
            print(f"❌ Device flow failed: {e}")
    
    await App.provide(".", lambda _: run_flow())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "device-flow":
        asyncio.run(demo_device_flow())
    else:
        asyncio.run(demo_auth_features())