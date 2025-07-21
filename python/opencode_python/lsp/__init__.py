"""Language Server Protocol integration."""

from .client import LSPClient, LSPManager
from .language import LANGUAGE_EXTENSIONS, get_language_id

__all__ = [
    "LSPClient",
    "LSPManager", 
    "LANGUAGE_EXTENSIONS",
    "get_language_id",
]