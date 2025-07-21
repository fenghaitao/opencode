"""OpenCode Python - AI coding agent for the terminal."""

__version__ = "0.1.0"
__author__ = "OpenCode Python Port"
__email__ = "dev@opencode.ai"
__description__ = "AI coding agent, built for the terminal - Python port"

from .app import App
from .config import Config
from .session import Session
from .tools import Tool

__all__ = ["App", "Config", "Session", "Tool"]