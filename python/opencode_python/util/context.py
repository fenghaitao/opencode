"""Context management utilities."""

from contextvars import ContextVar
from typing import Any, Callable, Dict, Generic, Optional, TypeVar, Union

T = TypeVar('T')


class Context(Generic[T]):
    """Context manager for dependency injection."""
    
    def __init__(self, name: str):
        self.name = name
        self._context_var: ContextVar[Optional[T]] = ContextVar(name, default=None)
    
    def use(self) -> T:
        """Get the current context value."""
        value = self._context_var.get()
        if value is None:
            raise RuntimeError(f"Context '{self.name}' not provided")
        return value
    
    def provide(self, value: T, callback: Callable[[], Union[T, Any]]) -> Any:
        """Provide context value for the duration of the callback."""
        token = self._context_var.set(value)
        try:
            return callback()
        finally:
            self._context_var.reset(token)
    
    async def provide_async(self, value: T, callback: Callable[[], Any]) -> Any:
        """Provide context value for the duration of the async callback."""
        token = self._context_var.set(value)
        try:
            return await callback()
        finally:
            self._context_var.reset(token)


def create(name: str) -> Context[T]:
    """Create a new context."""
    return Context[T](name)