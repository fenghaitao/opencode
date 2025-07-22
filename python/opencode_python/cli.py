"""Command-line interface for OpenCode Python."""

import asyncio
import os
import sys
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .app import App
from .config import Config
from .session import Session, Mode
from .provider import ProviderManager, OpenAIProvider, AnthropicProvider, GitHubCopilotProvider
from .auth import Auth, ApiKeyInfo
from .util.log import Log
from .server import Server
# TUI import is optional
try:
    from .tui import OpenCodeTUI
    TUI_AVAILABLE = OpenCodeTUI is not None
except ImportError:
    OpenCodeTUI = None
    TUI_AVAILABLE = False

app = typer.Typer(
    name="opencode",
    help="AI coding agent, built for the terminal",
    no_args_is_help=False,
    invoke_without_command=True
)

console = Console()


def print_logo():
    """Print the OpenCode logo."""
    logo = """
    ╔═══════════════════════════════════════╗
    ║                                       ║
    ║   ██████  ██████  ███████ ███    ██   ║
    ║  ██    ██ ██   ██ ██      ████   ██   ║
    ║  ██    ██ ██████  █████   ██ ██  ██   ║
    ║  ██    ██ ██      ██      ██  ██ ██   ║
    ║   ██████  ██      ███████ ██   ████   ║
    ║                                       ║
    ║   ██████  ██████  ██████  ███████     ║
    ║  ██      ██    ██ ██   ██ ██          ║
    ║  ██      ██    ██ ██   ██ █████       ║
    ║  ██      ██    ██ ██   ██ ██          ║
    ║   ██████  ██████  ██████  ███████     ║
    ║                                       ║
    ║           AI Coding Agent             ║
    ╚═══════════════════════════════════════╝
    """
    console.print(logo, style="bold blue")


@app.command()
def run(
    message: List[str] = typer.Argument(..., help="Message to send"),
    continue_session: bool = typer.Option(False, "--continue", "-c", help="Continue the last session"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to continue"),
    share: bool = typer.Option(False, "--share", help="Share the session"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use (provider/model)"),
    mode: Optional[str] = typer.Option(None, "--mode", help="Mode to use"),
    print_logs: bool = typer.Option(False, "--print-logs", help="Print logs to stderr"),
):
    """Run opencode with a message."""
    asyncio.run(_run_async(
        message, continue_session, session_id, share, model, mode, print_logs
    ))


async def _run_async(
    message: List[str],
    continue_session: bool,
    session_id: Optional[str],
    share: bool,
    model: Optional[str],
    mode: Optional[str],
    print_logs: bool,
):
    """Async implementation of run command."""
    # Initialize logging
    await Log.init(print_logs)
    
    # Join message parts
    message_text = " ".join(message)
    
    # Read from stdin if not a TTY
    if not sys.stdin.isatty():
        stdin_content = sys.stdin.read()
        if stdin_content.strip():
            message_text += "\n" + stdin_content
    
    if not message_text.strip():
        console.print("[red]Error: No message provided[/red]")
        return
    
    async def run_with_app(app_info):
        # Determine session
        session = None
        if continue_session:
            # Get the most recent session
            async for s in Session.list():
                session = s
                break
        elif session_id:
            session = await Session.get(session_id)
        
        if not session:
            session = await Session.create(mode or "default")
        
        # Print header
        print_logo()
        console.print()
        
        # Display message
        display_message = message_text[:300] + "..." if len(message_text) > 300 else message_text
        console.print(f"[bold]> {display_message}[/bold]")
        console.print()
        
        # Share session if requested
        if share:
            share_url = await Session.share(session.id)
            console.print(f"[blue]~ {share_url}[/blue]")
            console.print()
        
        # Display model info
        if model:
            provider_id, model_id = model.split("/", 1) if "/" in model else ("openai", model)
        else:
            # Use default model
            provider_id, model_id = "github-copilot", "gpt-4.1"
        
        console.print(f"[bold]@ {provider_id}/{model_id}[/bold]")
        console.print()
        
        # Parse and validate model
        # Map common model names to actual IDs
        model_aliases = {
            "claude-3-sonnet": "claude-3-5-sonnet-20241022",
            "claude-sonnet": "claude-3-5-sonnet-20241022", 
            "claude-haiku": "claude-3-haiku-20240307",
            "claude-opus": "claude-3-opus-20240229",
            "gpt-4": "gpt-4",
            "gpt-3.5": "gpt-3.5-turbo",
            # GitHub Copilot aliases (OpenAI models only)
            "copilot-gpt4": "gpt-4o",
            "copilot-gpt4-mini": "gpt-4o-mini",
            "copilot-gpt35": "gpt-3.5-turbo",
        }
        
        if model_id in model_aliases:
            model_id = model_aliases[model_id]
        
        # AI Integration
        try:
            # Register providers
            ProviderManager.register(OpenAIProvider())
            ProviderManager.register(AnthropicProvider())
            ProviderManager.register(GitHubCopilotProvider())
            
            # Get the provider
            provider = ProviderManager.get(provider_id)
            if not provider:
                console.print(f"[red]Provider '{provider_id}' not found[/red]")
                return
            
            # Check authentication
            if not await provider.is_authenticated():
                console.print(f"[red]Not authenticated with {provider_id}[/red]")
                console.print("Run: [cyan]opencode auth login[/cyan]")
                return
            
            # Create chat request
            from .provider.provider import ChatRequest, ChatMessage
            
            request = ChatRequest(
                messages=[
                    ChatMessage(role="user", content=message_text)
                ],
                model=model_id,
                max_tokens=4096
            )
            
            # Send request
            console.print("[dim]Thinking...[/dim]")
            response = await provider.chat(request)
            
            # Display response
            console.print("[bold]Response:[/bold]")
            console.print(response.content)
            
            if response.usage:
                console.print(f"\n[dim]Tokens: {response.usage['total_tokens']} ({response.usage['prompt_tokens']} + {response.usage['completion_tokens']})[/dim]")
            
            # Save to session (simplified)
            from .session.message import Message
            user_msg = Message(
                id=f"msg-{session.id}-user",
                session_id=session.id,
                role="user"
            )
            user_msg.add_text(message_text)
            
            assistant_msg = Message(
                id=f"msg-{session.id}-assistant", 
                session_id=session.id,
                role="assistant"
            )
            assistant_msg.add_text(response.content)
            
            await Session.add_message(session.id, user_msg)
            await Session.add_message(session.id, assistant_msg)
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print(f"[dim]Session ID: {session.id}[/dim]")
    
    await App.provide(".", run_with_app)


@app.command()
def serve(
    port: int = typer.Option(4096, "--port", "-p", help="Port to serve on"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to serve on"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
):
    """Start the OpenCode server."""
    asyncio.run(_serve_async(port, host, reload))


auth_app = typer.Typer(help="Manage authentication with AI providers")

@auth_app.command("login")
def auth_login():
    """Log in to a provider."""
    asyncio.run(_auth_login_async())

@auth_app.command("logout") 
def auth_logout():
    """Log out from a configured provider."""
    asyncio.run(_auth_logout_async())

@auth_app.command("list")
def auth_list():
    """List stored credentials."""
    asyncio.run(_auth_list_async())

app.add_typer(auth_app, name="auth")

@app.command()
def auth(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider to authenticate with"),
    list_providers: bool = typer.Option(False, "--list", "-l", help="List available providers"),
    check: bool = typer.Option(False, "--check", "-c", help="Check authentication status"),
):
    """Manage authentication with AI providers (legacy interface)."""
    asyncio.run(_auth_async(provider, list_providers, check))


async def _auth_async(provider: Optional[str], list_providers: bool, check: bool):
    """Async implementation of auth command."""
    async def auth_with_app(app_info):
        # Register providers
        ProviderManager.register(OpenAIProvider())
        ProviderManager.register(AnthropicProvider())
        
        if list_providers:
            console.print("[bold]Available Providers[/bold]")
            console.print()
            for p in ProviderManager.list():
                info = await p.get_info()
                status = "✓ Authenticated" if await p.is_authenticated() else "✗ Not authenticated"
                console.print(f"[blue]{info.id}[/blue] - {info.name}")
                console.print(f"  {status}")
                console.print(f"  [dim]{info.description}[/dim]")
                if info.auth_url:
                    console.print(f"  [dim]Get API key: {info.auth_url}[/dim]")
                console.print()
            return
        
        if check:
            console.print("[bold]Authentication Status[/bold]")
            console.print()
            for p in ProviderManager.list():
                info = await p.get_info()
                is_auth = await p.is_authenticated()
                status = "[green]✓ Authenticated[/green]" if is_auth else "[red]✗ Not authenticated[/red]"
                console.print(f"{info.name}: {status}")
            return
        
        if provider:
            p = ProviderManager.get(provider)
            if not p:
                console.print(f"[red]Provider '{provider}' not found[/red]")
                console.print("Available providers:")
                for provider_obj in ProviderManager.list():
                    info = await provider_obj.get_info()
                    console.print(f"  - {info.id}")
                return
            
            info = await p.get_info()
            console.print(f"[bold]Authenticating with {info.name}[/bold]")
            console.print()
            
            if await p.is_authenticated():
                console.print("[green]✓ Already authenticated[/green]")
                return
            
            console.print(f"To authenticate with {info.name}:")
            console.print(f"1. Get your API key from: {info.auth_url}")
            console.print(f"2. Set environment variable:")
            
            if provider == "openai":
                console.print("   [cyan]export OPENAI_API_KEY='your-api-key-here'[/cyan]")
            elif provider == "anthropic":
                console.print("   [cyan]export ANTHROPIC_API_KEY='your-api-key-here'[/cyan]")
            
            console.print("3. Run this command again to verify")
            return
        
        # No specific action, show help
        console.print("[bold]Authentication Management[/bold]")
        console.print()
        console.print("Usage:")
        console.print("  [cyan]opencode auth --list[/cyan]        List available providers")
        console.print("  [cyan]opencode auth --check[/cyan]       Check authentication status")
        console.print("  [cyan]opencode auth openai[/cyan]        Get OpenAI setup instructions")
        console.print("  [cyan]opencode auth anthropic[/cyan]     Get Anthropic setup instructions")
    
    await App.provide(".", auth_with_app)


async def _auth_login_async():
    """Async implementation of auth login command."""
    async def login_with_app(app_info):
        # Register providers
        ProviderManager.register(OpenAIProvider())
        ProviderManager.register(AnthropicProvider())
        ProviderManager.register(GitHubCopilotProvider())
        
        console.print("[bold]Add Credential[/bold]")
        console.print()
        
        # Get available providers
        providers = ProviderManager.list()
        provider_options = []
        
        # Priority order (matching TypeScript)
        priority = {"anthropic": 0, "github-copilot": 1, "openai": 2}
        
        # Sort providers by priority, then by name
        sorted_providers = sorted(providers, key=lambda x: (priority.get(x.id, 99), x.id))
        
        for p in sorted_providers:
            info = await p.get_info()
            hint = " (recommended)" if priority.get(p.id) == 0 else ""
            provider_options.append(f"{info.name}{hint}")
        
        # Store the sorted providers for selection
        providers = sorted_providers
        
        # Show provider selection
        console.print("Available providers:")
        for i, option in enumerate(provider_options, 1):
            console.print(f"  {i}. {option}")
        
        # Get user selection
        while True:
            try:
                selection = typer.prompt("Select provider (1-{})".format(len(provider_options)))
                provider_idx = int(selection) - 1
                if 0 <= provider_idx < len(providers):
                    selected_provider = providers[provider_idx]
                    break
                else:
                    console.print("[red]Invalid selection[/red]")
            except (ValueError, KeyboardInterrupt):
                console.print("\n[yellow]Cancelled[/yellow]")
                return
        
        provider_info = await selected_provider.get_info()
        console.print(f"\n[bold]Authenticating with {provider_info.name}[/bold]")
        
        # Handle GitHub Copilot OAuth flow
        if selected_provider.id == "github-copilot":
            try:
                console.print("Starting GitHub Copilot authentication...")
                
                # Start device flow
                device_info = await selected_provider.start_device_flow()
                
                console.print(f"\n[bold]Please visit:[/bold] [blue]{device_info['verification']}[/blue]")
                console.print(f"[bold]Enter code:[/bold] [yellow]{device_info['user']}[/yellow]")
                console.print("\n[dim]Waiting for authorization...[/dim]")
                
                # Poll for completion
                import asyncio
                while True:
                    await asyncio.sleep(device_info['interval'])
                    status = await selected_provider.poll_device_flow(device_info['device'])
                    
                    if status == "complete":
                        console.print("[green]✓ Login successful[/green]")
                        console.print("GitHub Copilot authentication completed.")
                        break
                    elif status == "failed":
                        console.print("[red]✗ Authentication failed[/red]")
                        break
                    elif status == "pending":
                        continue  # Keep polling
                    else:
                        console.print(f"[yellow]Status: {status}[/yellow]")
                        break
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Cancelled[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
        
        else:
            # API key authentication for other providers
            console.print(f"Get your API key from: [blue]{provider_info.auth_url}[/blue]")
            
            try:
                api_key = typer.prompt("Enter your API key", hide_input=True)
                if not api_key.strip():
                    console.print("[red]API key cannot be empty[/red]")
                    return
                
                # Test the API key
                console.print("Testing API key...")
                test_success = await selected_provider.authenticate(api_key=api_key)
                
                if test_success:
                    # Save the credential
                    auth_info = ApiKeyInfo(key=api_key)
                    await Auth.set(selected_provider.id, auth_info)
                    console.print("[green]✓ Login successful[/green]")
                    console.print("Credential saved securely.")
                else:
                    console.print("[red]✗ Invalid API key[/red]")
            
            except KeyboardInterrupt:
                console.print("\n[yellow]Cancelled[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
    
    await App.provide(".", login_with_app)


async def _auth_logout_async():
    """Async implementation of auth logout command."""
    async def logout_with_app(app_info):
        console.print("[bold]Remove Credential[/bold]")
        console.print()
        
        # Get stored credentials
        credentials = await Auth.all()
        if not credentials:
            console.print("[yellow]No credentials found[/yellow]")
            return
        
        # Register providers to get names
        ProviderManager.register(OpenAIProvider())
        ProviderManager.register(AnthropicProvider())
        ProviderManager.register(GitHubCopilotProvider())
        
        # Show credential options
        console.print("Stored credentials:")
        credential_list = list(credentials.items())
        
        for i, (provider_id, auth_info) in enumerate(credential_list, 1):
            provider = ProviderManager.get(provider_id)
            if provider:
                provider_info = await provider.get_info()
                name = provider_info.name
            else:
                name = provider_id
            
            console.print(f"  {i}. {name} ({auth_info.type})")
        
        # Get user selection
        while True:
            try:
                selection = typer.prompt("Select credential to remove (1-{})".format(len(credential_list)))
                cred_idx = int(selection) - 1
                if 0 <= cred_idx < len(credential_list):
                    provider_id, _ = credential_list[cred_idx]
                    break
                else:
                    console.print("[red]Invalid selection[/red]")
            except (ValueError, KeyboardInterrupt):
                console.print("\n[yellow]Cancelled[/yellow]")
                return
        
        # Confirm removal
        try:
            confirm = typer.confirm(f"Remove credential for {provider_id}?")
            if confirm:
                await Auth.remove(provider_id)
                console.print("[green]✓ Logout successful[/green]")
            else:
                console.print("[yellow]Cancelled[/yellow]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled[/yellow]")
    
    await App.provide(".", logout_with_app)


async def _auth_list_async():
    """Async implementation of auth list command."""
    async def list_with_app(app_info):
        auth_file_path = Auth.get_auth_file_path()
        console.print(f"[bold]Credentials[/bold] [dim]{auth_file_path}[/dim]")
        console.print()
        
        # Register providers
        ProviderManager.register(OpenAIProvider())
        ProviderManager.register(AnthropicProvider())
        ProviderManager.register(GitHubCopilotProvider())
        
        # Get stored credentials
        credentials = await Auth.all()
        
        if credentials:
            for provider_id, auth_info in credentials.items():
                provider = ProviderManager.get(provider_id)
                if provider:
                    provider_info = await provider.get_info()
                    name = provider_info.name
                else:
                    name = provider_id
                
                console.print(f"[blue]{name}[/blue] [dim]{auth_info.type}[/dim]")
            
            console.print()
            console.print(f"[dim]{len(credentials)} credentials[/dim]")
        else:
            console.print("[dim]No credentials stored[/dim]")
        
        # Check environment variables
        console.print()
        console.print("[bold]Environment Variables[/bold]")
        console.print()
        
        env_vars_found = []
        env_var_map = {
            "openai": ["OPENAI_API_KEY"],
            "anthropic": ["ANTHROPIC_API_KEY"],
            "github-copilot": [],  # OAuth only, no env vars
        }
        
        for provider_id, env_vars in env_var_map.items():
            for env_var in env_vars:
                if os.getenv(env_var):
                    provider = ProviderManager.get(provider_id)
                    if provider:
                        provider_info = await provider.get_info()
                        name = provider_info.name
                    else:
                        name = provider_id
                    
                    env_vars_found.append((name, env_var))
        
        if env_vars_found:
            for name, env_var in env_vars_found:
                console.print(f"[blue]{name}[/blue] [dim]{env_var}[/dim]")
            console.print()
            console.print(f"[dim]{len(env_vars_found)} environment variables[/dim]")
        else:
            console.print("[dim]No environment variables set[/dim]")
    
    await App.provide(".", list_with_app)


@app.command()
def models(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Filter by provider"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed model information"),
    authenticated_only: bool = typer.Option(False, "--auth-only", "-a", help="Show only models from authenticated providers"),
):
    """List available models."""
    asyncio.run(_list_models_async(provider, verbose, authenticated_only))


@app.command()
def sessions(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of sessions to show"),
):
    """List recent sessions."""
    asyncio.run(_list_sessions(limit))


async def _list_sessions(limit: int):
    """List recent sessions."""
    async def list_with_app():
        console.print("[bold]Recent Sessions[/bold]")
        console.print()
        
        count = 0
        async for session in Session.list():
            if count >= limit:
                break
            
            title = session.title or f"Session {session.id[:8]}"
            console.print(f"[blue]{session.id[:8]}[/blue] {title}")
            console.print(f"  [dim]Created: {session.created.strftime('%Y-%m-%d %H:%M')}[/dim]")
            console.print(f"  [dim]Messages: {session.message_count}[/dim]")
            console.print()
            count += 1
        
        if count == 0:
            console.print("[dim]No sessions found[/dim]")
    
    await App.provide(".", list_with_app)


@app.command()
def modes():
    """List available modes."""
    asyncio.run(_list_modes())


async def _list_modes():
    """List available modes."""
    async def list_with_app():
        console.print("[bold]Available Modes[/bold]")
        console.print()
        
        modes = await Mode.list()
        for mode in modes:
            console.print(f"[blue]{mode.name}[/blue] - {mode.description}")
            if mode.tools:
                console.print(f"  [dim]Tools: {', '.join(mode.tools)}[/dim]")
            console.print()
    
    await App.provide(".", list_with_app)


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    set_key: Optional[str] = typer.Option(None, "--set", help="Set configuration key"),
    value: Optional[str] = typer.Option(None, "--value", help="Configuration value"),
):
    """Manage configuration."""
    asyncio.run(_manage_config(show, set_key, value))


async def _list_models_async(provider_filter: Optional[str], verbose: bool, authenticated_only: bool):
    """Async implementation of models command."""
    async def list_models_with_app(app_info):
        # Register all providers
        ProviderManager.register(OpenAIProvider())
        ProviderManager.register(AnthropicProvider())
        ProviderManager.register(GitHubCopilotProvider())
        
        providers = ProviderManager.list()
        
        if not providers:
            console.print("[red]No providers available[/red]")
            return
        
        # Filter by provider if specified
        if provider_filter:
            providers = [p for p in providers if p.id == provider_filter]
            if not providers:
                console.print(f"[red]Provider '{provider_filter}' not found[/red]")
                console.print("Available providers:")
                for p in ProviderManager.list():
                    console.print(f"  - {p.id}")
                return
        
        # Filter by authentication status if requested
        if authenticated_only:
            authenticated_providers = []
            for p in providers:
                if await p.is_authenticated():
                    authenticated_providers.append(p)
            providers = authenticated_providers
            
            if not providers:
                console.print("[yellow]No authenticated providers found[/yellow]")
                console.print("Run: [cyan]opencode auth login[/cyan] to authenticate")
                return
        
        if verbose:
            # Detailed view
            console.print("[bold]Available Models[/bold]")
            console.print()
            
            for provider in providers:
                try:
                    provider_info = await provider.get_info()
                    is_authenticated = await provider.is_authenticated()
                    
                    # Provider header
                    auth_status = "[green]✓[/green]" if is_authenticated else "[red]✗[/red]"
                    console.print(f"[bold blue]{provider_info.name}[/bold blue] {auth_status}")
                    console.print(f"  [dim]{provider_info.description}[/dim]")
                    
                    if not is_authenticated and provider_info.auth_url:
                        console.print(f"  [dim]Get API key: {provider_info.auth_url}[/dim]")
                    
                    console.print()
                    
                    # Models
                    if provider_info.models:
                        for model in provider_info.models:
                            console.print(f"  [cyan]{provider.id}/{model.id}[/cyan]")
                            console.print(f"    {model.name}")
                            console.print(f"    [dim]{model.description}[/dim]")
                            
                            # Model capabilities
                            capabilities = []
                            if model.supports_tools:
                                capabilities.append("Tools")
                            if model.supports_streaming:
                                capabilities.append("Streaming")
                            if capabilities:
                                console.print(f"    [dim]Capabilities: {', '.join(capabilities)}[/dim]")
                            
                            # Context and cost info
                            console.print(f"    [dim]Context: {model.context_length:,} tokens[/dim]")
                            if model.cost_per_input_token is not None and model.cost_per_output_token is not None:
                                if model.cost_per_input_token == 0 and model.cost_per_output_token == 0:
                                    console.print(f"    [dim]Cost: Free (with subscription)[/dim]")
                                else:
                                    console.print(f"    [dim]Cost: ${model.cost_per_input_token:.6f}/1K input, ${model.cost_per_output_token:.6f}/1K output[/dim]")
                            
                            console.print()
                    else:
                        console.print("  [dim]No models available[/dim]")
                        console.print()
                
                except Exception as e:
                    console.print(f"  [red]Error loading provider info: {e}[/red]")
                    console.print()
        else:
            # Simple list view (like TypeScript version)
            console.print("[bold]Available Models[/bold]")
            console.print()
            
            model_count = 0
            for provider in providers:
                try:
                    provider_info = await provider.get_info()
                    is_authenticated = await provider.is_authenticated()
                    
                    for model in provider_info.models:
                        auth_indicator = "" if is_authenticated else " [dim](not authenticated)[/dim]"
                        console.print(f"[cyan]{provider.id}/{model.id}[/cyan]{auth_indicator}")
                        model_count += 1
                
                except Exception as e:
                    console.print(f"[red]Error loading {provider.id}: {e}[/red]")
            
            if model_count == 0:
                console.print("[dim]No models available[/dim]")
            else:
                console.print()
                console.print(f"[dim]{model_count} models available[/dim]")
                
                if not authenticated_only:
                    # Show authentication hint
                    unauthenticated_count = 0
                    for provider in providers:
                        if not await provider.is_authenticated():
                            provider_info = await provider.get_info()
                            unauthenticated_count += len(provider_info.models)
                    
                    if unauthenticated_count > 0:
                        console.print(f"[dim]{unauthenticated_count} models require authentication[/dim]")
                        console.print("[dim]Run: [cyan]opencode auth login[/cyan] to authenticate[/dim]")
    
    await App.provide(".", list_models_with_app)


async def _manage_config(show: bool, set_key: Optional[str], value: Optional[str]):
    """Manage configuration."""
    async def config_with_app():
        if show:
            config = await Config.get()
            console.print("[bold]Current Configuration[/bold]")
            console.print()
            console.print(f"Log Level: {config.log_level or 'INFO'}")
            console.print(f"Auto Share: {config.autoshare}")
            console.print(f"Default Provider: {config.default_provider or 'None'}")
            console.print(f"Default Model: {config.default_model or 'None'}")
        elif set_key and value:
            await Config.update({set_key: value})
            console.print(f"[green]Set {set_key} = {value}[/green]")
        else:
            console.print("[yellow]Use --show to view config or --set/--value to update[/yellow]")
    
    await App.provide(".", config_with_app)


async def _serve_async(port: int, host: str, reload: bool):
    """Async implementation of serve command."""
    async def serve_with_app(app_info):
        # Check if providers are available
        has_providers = await Server.check_providers()
        if not has_providers:
            console.print("[red]No providers available[/red]")
            console.print("You need to configure at least one provider to use the server.")
            console.print("Run: [cyan]opencode auth login[/cyan] to set up authentication")
            return
        
        console.print("[bold]Starting OpenCode Server[/bold]")
        console.print()
        console.print(f"[blue]Host:[/blue] {host}")
        console.print(f"[blue]Port:[/blue] {port}")
        console.print(f"[blue]Reload:[/blue] {reload}")
        console.print()
        console.print(f"[green]Server will be available at:[/green] [cyan]http://{host}:{port}[/cyan]")
        console.print(f"[green]API documentation:[/green] [cyan]http://{host}:{port}/docs[/cyan]")
        console.print(f"[green]OpenAPI spec:[/green] [cyan]http://{host}:{port}/doc[/cyan]")
        console.print()
        console.print("[dim]Press Ctrl+C to stop the server[/dim]")
        console.print()
        
        # Create and run server
        from .server.server import ServerConfig
        config = ServerConfig(port=port, host=host, reload=reload)
        server = Server(config)
        
        try:
            await server.serve()
        except KeyboardInterrupt:
            console.print("\n[yellow]Server stopped[/yellow]")
        except Exception as e:
            console.print(f"\n[red]Server error: {e}[/red]")
    
    await App.provide(".", serve_with_app)


@app.command()
def tui(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use (provider/model)"),
    mode: Optional[str] = typer.Option(None, "--mode", help="Mode to use"),
    project: Optional[str] = typer.Option(None, "--project", help="Project directory"),
):
    """Start the OpenCode Terminal User Interface."""
    if not TUI_AVAILABLE:
        console.print("[red]TUI not available[/red]")
        console.print("Install textual with: [cyan]pip install textual[/cyan]")
        return
    
    asyncio.run(_tui_async(model, mode, project))


async def _tui_async(model: Optional[str], mode: Optional[str], project: Optional[str]):
    """Async implementation of TUI command."""
    async def tui_with_app(app_info):
        console.print("[bold]Starting OpenCode TUI[/bold]")
        console.print()
        
        if model:
            console.print(f"[blue]Model:[/blue] {model}")
        if mode:
            console.print(f"[blue]Mode:[/blue] {mode}")
        if project:
            console.print(f"[blue]Project:[/blue] {project}")
        
        console.print("[dim]Loading interface...[/dim]")
        console.print()
        
        try:
            # Import and run TUI
            from .tui.app import OpenCodeTUI
            
            # Create TUI app with initial settings
            tui_app = OpenCodeTUI()
            
            # Set initial model if provided
            if model and "/" in model:
                provider_id, model_id = model.split("/", 1)
                # Store for later use in TUI
                tui_app.initial_provider = provider_id
                tui_app.initial_model = model_id
            
            # Run the TUI
            await tui_app.run_async()
            
        except ImportError as e:
            console.print(f"[red]TUI dependencies not available: {e}[/red]")
            console.print("Install with: [cyan]pip install textual[/cyan]")
        except KeyboardInterrupt:
            console.print("\n[yellow]TUI stopped[/yellow]")
        except Exception as e:
            console.print(f"[red]TUI error: {e}[/red]")
    
    # Change to project directory if specified
    if project:
        import os
        try:
            os.chdir(project)
        except Exception as e:
            console.print(f"[red]Failed to change to project directory: {e}[/red]")
            return
    
    await App.provide(".", tui_with_app)


@app.callback()
def main_callback(ctx: typer.Context):
    """Main callback for handling no-command invocation."""
    if ctx.invoked_subcommand is None:
        # No subcommand provided, launch TUI
        if not TUI_AVAILABLE:
            console.print("[red]TUI not available[/red]")
            console.print("Install textual with: [cyan]pip install textual[/cyan]")
            console.print()
            console.print("Or use a specific command:")
            console.print("  [cyan]opencode run 'your message'[/cyan]")
            console.print("  [cyan]opencode --help[/cyan]")
            return
        
        # Launch TUI with default settings
        asyncio.run(_tui_async(None, None, None))


def cli_main():
    """CLI entry point wrapper."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    cli_main()