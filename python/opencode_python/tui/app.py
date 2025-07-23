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
from ..provider.provider import ChatRequest, ChatMessage as ProviderChatMessage
from ..session import Session, Mode
from ..session.session import SessionChatRequest, StreamingSessionResponse
from ..config import Config
from ..util.log import Log as Logger
from ..tools import ToolRegistry


class ChatMessageWidget(Static):
    """A single chat message widget."""
    
    def __init__(self, role: str, content: str, **kwargs):
        self.role = role
        self.content = content
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        role_style = "bold blue" if self.role == "user" else "bold green"
        yield Static(f"[{role_style}]{self.role.upper()}[/{role_style}]", classes="message-role")
        
        # Store reference to content widget for streaming updates
        self.content_widget = Static(self.content, classes="message-content")
        yield self.content_widget
    
    def update_content(self, new_content: str):
        """Update the content of this message widget (for streaming)."""
        self.content = new_content
        try:
            # Try to render as markdown, fallback to plain text
            markdown = Markdown(new_content)
            self.content_widget.update(markdown)
        except Exception:
            # Fallback to plain text
            self.content_widget.update(new_content)


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
        
        # Remove welcome message if it exists (first real message)
        messages_container = self.query_one("#messages-container")
        try:
            welcome_widget = messages_container.query_one("#welcome-message")
            welcome_widget.remove()
        except:
            pass  # Welcome message doesn't exist, that's fine
        
        # Add message widget
        message_widget = ChatMessageWidget(role, content)
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
        # Always create a new welcome message since we removed all children
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
        
        # Sort providers to prioritize GitHub Copilot
        priority_order = {"github-copilot": 0, "anthropic": 1, "openai": 2}
        sorted_providers = sorted(self.providers, key=lambda p: priority_order.get(p.id, 99))
        
        for provider in sorted_providers:
            try:
                provider_info = await provider.get_info()
                is_auth = await provider.is_authenticated()
                status = "[OK]" if is_auth else "[--]"
                recommended = " (recommended)" if provider.id == "github-copilot" else ""
                provider_options.append((f"{status} {provider_info.name}{recommended}", provider.id))
                
                # Store models for this provider
                self.models[provider.id] = provider_info.models
            except Exception as e:
                self.log.error(f"Error loading provider {provider.id}: {str(e)}")
        
        # Update provider select
        provider_select = self.query_one("#provider-select", Select)
        provider_select.set_options(provider_options)
        
        # Auto-select GitHub Copilot if authenticated
        for provider in sorted_providers:
            if provider.id == "github-copilot" and await provider.is_authenticated():
                self.selected_provider = provider.id
                provider_select.value = provider.id
                self._update_model_select()
                # Auto-select gpt-4.1 if available
                await self._auto_select_default_model()
                break
    
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
        
        # Auto-select default model after updating options
        self.call_after_refresh(self._auto_select_default_model)
    
    async def _auto_select_default_model(self):
        """Auto-select the default model for the current provider."""
        if not self.selected_provider or self.selected_provider not in self.models:
            return
        
        # Define preferred models for each provider
        preferred_models = {
            "github-copilot": "gpt-4.1",
            "openai": "gpt-4",
            "anthropic": "claude-3-5-sonnet-20241022"
        }
        
        available_models = [m.id for m in self.models[self.selected_provider]]
        preferred_model = preferred_models.get(self.selected_provider)
        
        # Try to select the preferred model, or fall back to first available
        if preferred_model and preferred_model in available_models:
            target_model = preferred_model
        elif available_models:
            target_model = available_models[0]
        else:
            return
        
        # Update the selection
        self.selected_model = target_model
        model_select = self.query_one("#model-select", Select)
        model_select.value = target_model
        self._update_model_info()
    
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
            yield Button("Toggle Streaming", id="toggle-streaming-button")
            yield Static("Mode: Streaming", id="streaming-mode-text")


class OpenCodeTUI(App):
    """Main OpenCode TUI application."""
    
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 2;
        grid-rows: auto 1fr;
        grid-columns: 1fr 2fr 1fr;
    }
    
    #header-container {
        column-span: 3;
        height: 1;
    }
    
    #custom-header {
        background: $primary;
        color: $text;
        text-align: center;
        padding: 0 1;
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
        Binding("ctrl+n", "action_new_session", "New Session"),
        Binding("ctrl+l", "action_clear_chat", "Clear Chat"),
        Binding("ctrl+t", "action_toggle_streaming", "Toggle Streaming"),
        Binding("enter", "action_send_message", "Send", show=False),
        Binding("f1", "action_show_help", "Help"),
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_session = None
        self.app_info = None
        self._creating_session = False  # Flag to prevent concurrent session creation
        self.streaming_mode = True  # Default to streaming mode
        # Use Textual's built-in logging instead of custom logger
        # self._logger = Logger.create({"service": "tui"})
    
    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        # Custom header with ASCII characters only
        with Container(id="header-container"):
            yield Static("OpenCode TUI - AI Coding Assistant | Press Ctrl+C to quit, F1 for help", id="custom-header")
        
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
            try:
                self.app_info = OpenCodeApp.info()
                
                # Load providers
                model_selector = self.query_one(ModelSelector)
                await model_selector.load_providers()
                
                # Create initial session
                await self._create_new_session()
                
                # Update status
                await self._update_status("Ready - Select a model and start chatting!")
                
            except Exception as e:
                self.log.error(f"Failed to initialize app: {str(e)}")
                await self._update_status(f"Initialization error: {str(e)}")
        
        await OpenCodeApp.provide(".", lambda _: init_app())
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "send-button":
            await self.action_send_message()
        elif event.button.id == "new-session-button":
            await self.action_new_session()
        elif event.button.id == "clear-chat-button":
            await self.action_clear_chat()
        elif event.button.id == "toggle-streaming-button":
            await self.action_toggle_streaming()
    
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
        
        # Update status based on mode
        mode_text = "streaming enabled" if self.streaming_mode else "non-streaming mode"
        await self._update_status(f"Thinking... ({mode_text})")
        
        try:
            # Get provider
            provider = ProviderManager.get(model_selector.selected_provider)
            if not provider:
                raise Exception(f"Provider {model_selector.selected_provider} not found")
            
            # Check authentication
            if not await provider.is_authenticated():
                raise Exception(f"Not authenticated with {model_selector.selected_provider}")
            
            # Create session chat request with integrated system prompts and tools
            session_request = SessionChatRequest(
                session_id=self.current_session.id if self.current_session else "temp-session",
                provider_id=model_selector.selected_provider,
                model_id=model_selector.selected_model,
                mode="default",  # TODO: Make this configurable
                message_content=message
            )
            
            if self.streaming_mode:
                # Send streaming request through session system
                streaming_response = await Session.chat_streaming(session_request)
                
                # Handle streaming response
                await self._handle_streaming_response(streaming_response, chat_panel)
            else:
                # Send non-streaming request
                response = await Session.chat(session_request)
                
                # Add the complete response at once
                chat_panel.add_message("assistant", response.content)
                
                # Update status with completion info
                usage = response.usage
                tokens_info = ""
                if usage:
                    total = usage.get('total_tokens', 0)
                    tokens_info = f" ({total} tokens)"
                
                await self._update_status(f"Response complete{tokens_info}")
            
        except Exception as e:
            self.log.error(f"Chat error: {str(e)}")
            chat_panel.add_message("system", f"Error: {str(e)}")
            await self._update_status(f"Error: {str(e)}")
    
    async def action_new_session(self) -> None:
        """Create a new session."""
        if self._creating_session:
            await self._update_status("Session creation already in progress...")
            return
            
        try:
            self._creating_session = True
            await self._update_status("Creating new session...")
            await self._create_new_session()
            await self.action_clear_chat()
            await self._update_status("New session created")
        except Exception as e:
            self.log.error(f"Failed to create new session: {str(e)}")
            await self._update_status(f"Failed to create new session: {str(e)}")
        finally:
            self._creating_session = False
    
    async def action_clear_chat(self) -> None:
        """Clear the chat."""
        chat_panel = self.query_one(ChatPanel)
        chat_panel.clear_messages()
        await self._update_status("Chat cleared")
    
    async def action_toggle_streaming(self) -> None:
        """Toggle between streaming and non-streaming modes."""
        self.streaming_mode = not self.streaming_mode
        mode_text = "Streaming" if self.streaming_mode else "Non-Streaming"
        
        # Update the mode display
        streaming_mode_text = self.query_one("#streaming-mode-text", Static)
        streaming_mode_text.update(f"Mode: {mode_text}")
        
        await self._update_status(f"Switched to {mode_text.lower()} mode")
    
    async def action_show_help(self) -> None:
        """Show help information."""
        help_text = """
# OpenCode TUI Help

## Key Bindings
- **Ctrl+C**: Quit application
- **Ctrl+N**: New session
- **Ctrl+L**: Clear chat
- **Ctrl+T**: Toggle streaming/non-streaming mode
- **Enter**: Send message (when in input field)
- **F1**: Show this help

## Usage
1. Select a provider and model from the left panel
2. Type your message in the input field
3. Press Enter or click Send to chat with the AI
4. Use the right panel for session management

## Tools Available
The AI has access to these tools:
- **bash**: Execute shell commands
- **read**: Read file contents
- **write**: Write to files
- **edit**: Edit files
- **grep**: Search in files
- **ls**: List directory contents
- **multiedit**: Multi-file editing
- **patch**: Apply patches
- **task**: Task management
- **todo**: Todo management
- **webfetch**: Web content fetching
- **lsp**: Language server integration

Tools are automatically integrated with system prompts and context.

## Authentication
Make sure you're authenticated with your chosen provider:
- Run `opencode auth login` in terminal
- Or set environment variables (OPENAI_API_KEY, etc.)
"""
        chat_panel = self.query_one(ChatPanel)
        chat_panel.add_message("system", help_text)
    
    async def _create_new_session(self) -> None:
        """Create a new session."""
        try:
            async def create_session():
                self.current_session = await Session.create(mode="default")
                return self.current_session
            
            session = await OpenCodeApp.provide(".", lambda _: create_session())
            
            # Update session info
            session_info = self.query_one("#session-info", Static)
            session_info.update(f"Session: {session.id[:8]}")
            
        except Exception as e:
            self.log.error(f"Failed to create session: {str(e)}")
            await self._update_status(f"Failed to create session: {str(e)}")
            # Set a fallback session info
            session_info = self.query_one("#session-info", Static)
            session_info.update("Session: Error")
    
    async def _handle_streaming_response(self, streaming_response: StreamingSessionResponse, chat_panel) -> None:
        """Handle streaming response from the session system."""
        current_message_widget = None
        tool_count = 0
        total_content = ""
        chunk_count = 0

        try:
            self.log.info("Starting streaming response handling")

            async for chunk in streaming_response:
                chunk_count += 1
                chunk_type = chunk.get("type", "")
                content = chunk.get("content", "")

                self.log.debug(f"Processing chunk {chunk_count}: type={chunk_type}, content_len={len(content)}")
                
                if chunk_type == "content":
                    total_content += content

                    # Stream content to the chat
                    if current_message_widget is None:
                        # Create new assistant message widget
                        self.log.debug("Creating new assistant message widget")
                        current_message_widget = ChatMessageWidget("assistant", total_content)
                        messages_container = chat_panel.query_one("#messages-container")
                        messages_container.mount(current_message_widget)
                    else:
                        # Update existing message content using the new method
                        current_message_widget.update_content(total_content)

                    # Scroll to bottom
                    try:
                        chat_panel.call_after_refresh(chat_panel._scroll_to_bottom)
                    except Exception as scroll_error:
                        self.log.error(f"Scroll failed: {scroll_error}")
                
                elif chunk_type == "status":
                    await self._update_status(content)
                
                elif chunk_type == "tool_start":
                    await self._update_status(content)
                    chat_panel.add_message("system", f"[TOOL] {content}")
                
                elif chunk_type == "tool_result":
                    chat_panel.add_message("system", f"[RESULT] {content}")
                    tool_count += 1
                
                elif chunk_type == "tool_error":
                    chat_panel.add_message("system", f"[ERROR] {content}")
                    tool_count += 1
                
                elif chunk_type == "error":
                    chat_panel.add_message("system", f"Error: {content}")
                    await self._update_status(f"Error: {content}")
                    break
                
                elif chunk_type == "complete":
                    # Final status update
                    usage = chunk.get("usage")
                    tokens_info = ""
                    if usage:
                        total = usage.get('total_tokens', 0)
                        tokens_info = f" ({total} tokens)"
                    
                    tool_info = f" (used {tool_count} tools)" if tool_count > 0 else ""
                    await self._update_status(f"Response complete{tokens_info}{tool_info}")
                    break
                
                # Small delay to make streaming visible
                await asyncio.sleep(0.02)
                
        except Exception as e:
            self.log.error(f"Streaming error: {str(e)}")
            await self._update_status(f"Streaming error: {str(e)}")
        
        finally:
            # Log final state
            self.log.info(f"Streaming complete - Total chunks: {chunk_count}, content length: {len(total_content)}")
            if current_message_widget:
                self.log.debug(f"Final widget content length: {len(current_message_widget.content)}")
            else:
                self.log.warning("No message widget was created during streaming")
    
    async def _update_status(self, message: str) -> None:
        """Update status message."""
        status_text = self.query_one("#status-text", Static)
        # Escape markup characters to prevent MarkupError
        escaped_message = message.replace("[", "\\[").replace("]", "\\]")
        status_text.update(escaped_message)


def run_tui():
    """Run the TUI application."""
    app = OpenCodeTUI()
    app.run()