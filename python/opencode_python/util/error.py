"""Error handling utilities."""

from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel


class NamedError(Exception):
    """Base class for named errors with structured data."""
    
    def __init__(self, data: Optional[Dict[str, Any]] = None, message: Optional[str] = None, cause: Optional[Exception] = None):
        self.data = data or {}
        self.message = message or self.__class__.__name__
        self.cause = cause
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "name": self.__class__.__name__,
            "message": self.message,
            "data": self.data,
            "cause": str(self.cause) if self.cause else None,
        }
    
    @classmethod
    def create(cls, name: str, schema: Optional[Type[BaseModel]] = None) -> Type["NamedError"]:
        """Create a new named error class."""
        
        class CustomError(NamedError):
            def __init__(self, data: Optional[Dict[str, Any]] = None, message: Optional[str] = None, cause: Optional[Exception] = None):
                if schema and data:
                    # Validate data against schema if provided
                    try:
                        schema(**data)
                    except Exception as e:
                        raise ValueError(f"Invalid error data for {name}: {e}") from e
                super().__init__(data, message, cause)
        
        CustomError.__name__ = name
        CustomError.__qualname__ = name
        return CustomError


# Common error types
class ConfigError(NamedError):
    """Configuration related errors."""
    pass


class SessionError(NamedError):
    """Session related errors."""
    pass


class ToolError(NamedError):
    """Tool execution errors."""
    pass


class LSPError(NamedError):
    """LSP related errors."""
    pass


class ProviderError(NamedError):
    """AI provider related errors."""
    pass