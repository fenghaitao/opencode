"""Main TUI application using Textual framework."""

import asyncio
from typing import Optional, List, Dict, Any

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header, Footer, Input, Static, Button, 
    DataTable, Tabs, Tab, TextArea, Log, 
    LoadingIndicator, Label, Select
)
from textual.reactive import reactive
from textual.message import Message
from textual.binding import Binding
from textual import events
from rich.text import Text
from rich.markdown import Markdown

from ..app import App as OpenCodeApp
from ..provider import ProviderManager, OpenAIProvider, AnthropicProvider, GitHubCopilotProvider
from ..provider.provider import ChatRequest, ChatMessage
from ..session import Session, Mode
from ..config import Config
from ..util.log import Log as Logger


class ChatMessage(Static):
    """A single chat message widget."""
    
    def __init__(self, role: str, content: str, **kwargs):
        self.role = role
        self.content = content
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        role_style = "bold blue" if self.role == "user" else "bold green"
        yield Static(f"[{role_style}]{self.role.upper()}[/{role_style}]", classes="message-role")
        
        # Render markdown content
        if self.content.strip():
            try:
                markdown = Markdown(self.content)
                yield Static(markdown, classes="message-content")
            except Exception:
                # Fallback to plain text if markdown fails
                yield Static(self.content, classes="message-content")


class ChatPanel(Container):
    """Chat messages and input panel."""
    
    messages: reactive[List[Dict[str, str]]] = reactive([])
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.message_widgets = []
    
    def compose(self) -> ComposeResult:
        with Vertical(id="chat-container"):
            with Container(id="messages-container"):
                yield Static("Welcome to OpenCode! Start a conversation below.", id="welcome-message")
            with Horizontal(id="input-container"):
                yield Input(placeholder="Type your message here...", id="message-input")
                yield Button("Send", variant="primary", id="send-button")
    
    def add_message(self, role: str, content: str):
        """Add a new message to the chat."""
        self.messages = self.messages + [{"role": role, "content": content}]
        
        # Add message widget
        message_widget = ChatMessage(role, content)
        messages_container = self.query_one("#messages-container")
        messages_container.mount(message_widget)
        
        # Scroll to bottom
        self.call_after_refresh(self._scroll_to_bottom)
    
    def _scroll_to_bottom(self):
        """Scroll to the bottom of the messages."""
        messages_container = self.query_one("#messages-container")
        if hasattr(messages_container, 'scroll_end'):
            messages_container.scroll_end()
    
    def clear_messages(self):
        """Clear all messages."""
        self.messages = []
        messages_container = self.query_one("#messages-container")
        messages_container.remove_children()
        messages_container.mount(Static("Chat cleared. Start a new conversation!", id="welcome-message"))


class ModelSelector(Container):
    """Model selection panel."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.providers = []
        self.models = {}
        self.selected_provider = None
        self.selected_model = None
    
    def compose(self) -> ComposeResult:
        with Vertical(id="model-selector"):
            yield Label("Model Selection", classes="panel-title")
            yield Select([], prompt="Select Provider", id="provider-select")
            yield Select([], prompt="Select Model", id="model-select", disabled=True)
            yield Static("", id="model-info")
    
    async def load_providers(self):
        """Load available providers and models."""
        # Register providers
        ProviderManager.register(OpenAIProvider())
        ProviderManager.register(AnthropicProvider())
        ProviderManager.register(GitHubCopilotProvider())
        
        self.providers = ProviderManager.list()
        provider_options = []
        
        for provider in self.providers:
            try:
                provider_info = await provider.get_info()
                is_auth = await provider.is_authenticated()
                status = "✓" if is_auth else "✗"
                provider_options.append((f"{status} {provider_info.name}", provider.id))
                
                # Store models for this provider
                self.models[provider.id] = provider_info.models
            except Exception as e:
                self.log.error(f"Error loading provider {provider.id}: {str(e)}")
        
        # Update provider select
        provider_select = self.query_one("#provider-select", Select)
        provider_select.set_options(provider_options)
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle selection changes."""
        if event.select.id == "provider-select":
            self.selected_provider = event.value
            self._update_model_select()
        elif event.select.id == "model-select":
            self.selected_model = event.value
            self._update_model_info()
    
    def _update_model_select(self):
        """Update model selection based on provider."""
        if not self.selected_provider or self.selected_provider not in self.models:
            return
        
        model_options = []
        for model in self.models[self.selected_provider]:
            model_options.append((model.name, model.id))
        
        model_select = self.query_one("#model-select", Select)
        model_select.set_options(model_options)
        model_select.disabled = False
    
    def _update_model_info(self):
        """Update model information display."""
        if not self.selected_provider or not self.selected_model:
            return
        
        models = self.models.get(self.selected_provider, [])
        selected_model = next((m for m in models if m.id == self.selected_model), None)
        
        if selected_model:
            info_text = f"""
**{selected_model.name}**
{selected_model.description}

Context: {selected_model.context_length:,} tokens
Tools: {'Yes' if selected_model.supports_tools else 'No'}
Streaming: {'Yes' if selected_model.supports_streaming else 'No'}
"""
            if selected_model.cost_per_input_token is not None:
                if selected_model.cost_per_input_token == 0:
                    info_text += "\nCost: Free (with subscription)"
                else:
                    info_text += f"\nCost: ${selected_model.cost_per_input_token:.6f}/1K input"
            
            model_info = self.query_one("#model-info", Static)
            model_info.update(Markdown(info_text))


class StatusPanel(Container):
    """Status and information panel."""
    
    def compose(self) -> ComposeResult:
        with Vertical(id="status-panel"):
            yield Label("Status", classes="panel-title")
            yield Static("Ready", id="status-text")
            yield Static("", id="session-info")
            yield Button("New Session", id="new-session-button")
            yield Button("Clear Chat", id="clear-chat-button")


class OpenCodeTUI(App):
    """Main OpenCode TUI application."""
    
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 1;
        grid-columns: 1fr 2fr 1fr;
    }
    
    #left-panel {
        background: $surface;
        border-right: solid $primary;
    }
    
    #center-panel {
        background: $background;
    }
    
    #right-panel {
        background: $surface;
        border-left: solid $primary;
    }
    
    .panel-title {
        background: $primary;
        color: $text;
        text-align: center;
        padding: 1;
        margin-bottom: 1;
    }
    
    #messages-container {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }
    
    #input-container {
        height: auto;
        padding: 1;
    }
    
    #message-input {
        width: 1fr;
        margin-right: 1;
    }
    
    .message-role {
        margin-top: 1;
        margin-bottom: 0;
    }
    
    .message-content {
        margin-bottom: 1;
        padding-left: 2;
    }
    
    #model-selector, #status-panel {
        padding: 1;
    }
    
    Button {
        margin: 1 0;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+n", "new_session", "New Session"),
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
        Binding("enter", "send_message", "Send", show=False),
        Binding("f1", "show_help", "Help"),
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_session = None
        self.app_info = None
        # Use Textual's built-in logging instead of custom logger
        # self._logger = Logger.create({"service": "tui"})
    
    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()
        
        with Container(id="left-panel"):
            yield ModelSelector()
        
        with Container(id="center-panel"):
            yield ChatPanel()
        
        with Container(id="right-panel"):
            yield StatusPanel()
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize the application."""
        self.title = "OpenCode TUI"
        self.sub_title = "AI Coding Assistant"
        
        # Initialize within app context
        async def init_app():
            self.app_info = OpenCodeApp.info()
            
            # Load providers
            model_selector = self.query_one(ModelSelector)
            await model_selector.load_providers()
            
            # Create initial session
            await self._create_new_session()
            
            # Update status
            await self._update_status("Ready - Select a model and start chatting!")
        
        await OpenCodeApp.provide(".", lambda _: init_app())
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "send-button":
            await self.action_send_message()
        elif event.button.id == "new-session-button":
            await self.action_new_session()
        elif event.button.id == "clear-chat-button":
            await self.action_clear_chat()
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "message-input":
            await self.action_send_message()
    
    async def action_send_message(self) -> None:
        """Send a message to the AI."""
        message_input = self.query_one("#message-input", Input)
        message = message_input.value.strip()
        
        if not message:
            return
        
        # Clear input
        message_input.value = ""
        
        # Get selected model
        model_selector = self.query_one(ModelSelector)
        if not model_selector.selected_provider or not model_selector.selected_model:
            await self._update_status("Please select a provider and model first!")
            return
        
        # Add user message to chat
        chat_panel = self.query_one(ChatPanel)
        chat_panel.add_message("user", message)
        
        # Update status
        await self._update_status("Thinking...")
        
        try:
            # Get provider
            provider = ProviderManager.get(model_selector.selected_provider)
            if not provider:
                raise Exception(f"Provider {model_selector.selected_provider} not found")
            
            # Check authentication
            if not await provider.is_authenticated():
                raise Exception(f"Not authenticated with {model_selector.selected_provider}")
            
            # Create chat request
            request = ChatRequest(
                messages=[ChatMessage(role="user", content=message)],
                model=model_selector.selected_model,
                max_tokens=4096
            )
            
            # Send request
            response = await provider.chat(request)
            
            # Add assistant response
            chat_panel.add_message("assistant", response.content)
            
            # Update status
            tokens_info = ""
            if response.usage:
                total = response.usage.get('total_tokens', 0)
                tokens_info = f" ({total} tokens)"
            
            await self._update_status(f"Response received{tokens_info}")
            
        except Exception as e:
            self.log.error(f"Chat error: {str(e)}")
            chat_panel.add_message("system", f"Error: {str(e)}")
            await self._update_status(f"Error: {str(e)}")
    
    async def action_new_session(self) -> None:
        """Create a new session."""
        await self._create_new_session()
        await self.action_clear_chat()
        await self._update_status("New session created")
    
    async def action_clear_chat(self) -> None:
        """Clear the chat."""
        chat_panel = self.query_one(ChatPanel)
        chat_panel.clear_messages()
        await self._update_status("Chat cleared")
    
    async def action_show_help(self) -> None:
        """Show help information."""
        help_text = """
# OpenCode TUI Help

## Key Bindings
- **Ctrl+C**: Quit application
- **Ctrl+N**: New session
- **Ctrl+L**: Clear chat
- **Enter**: Send message (when in input field)
- **F1**: Show this help

## Usage
1. Select a provider and model from the left panel
2. Type your message in the input field
3. Press Enter or click Send to chat with the AI
4. Use the right panel for session management

## Authentication
Make sure you're authenticated with your chosen provider:
- Run `opencode auth login` in terminal
- Or set environment variables (OPENAI_API_KEY, etc.)
"""
        chat_panel = self.query_one(ChatPanel)
        chat_panel.add_message("system", help_text)
    
    async def _create_new_session(self) -> None:
        """Create a new session."""
        async def create_session():
            self.current_session = await Session.create("default")
            return self.current_session
        
        session = await OpenCodeApp.provide(".", lambda _: create_session())
        
        # Update session info
        session_info = self.query_one("#session-info", Static)
        session_info.update(f"Session: {session.id[:8]}")
    
    async def _update_status(self, message: str) -> None:
        """Update status message."""
        status_text = self.query_one("#status-text", Static)
        status_text.update(message)


def run_tui():
    """Run the TUI application."""
    app = OpenCodeTUI()
    app.run()