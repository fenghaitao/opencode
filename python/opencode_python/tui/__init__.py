"""Terminal User Interface for OpenCode Python."""

try:
    from .app import OpenCodeTUI
    __all__ = ["OpenCodeTUI"]
except ImportError:
    # Textual not available
    OpenCodeTUI = None
    __all__ = []