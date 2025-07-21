"""Event bus for inter-component communication."""

import asyncio
from typing import Any, Callable, Dict, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


class Event(BaseModel):
    """Base event class."""
    
    type: str
    properties: Dict[str, Any]


class EventBus:
    """Simple event bus for pub/sub communication."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = {}
        self._async_subscribers: Dict[str, List[Callable[[Event], Any]]] = {}
    
    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> Callable[[], None]:
        """Subscribe to an event type. Returns unsubscribe function."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        self._subscribers[event_type].append(handler)
        
        def unsubscribe():
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(handler)
                except ValueError:
                    pass
        
        return unsubscribe
    
    def subscribe_async(self, event_type: str, handler: Callable[[Event], Any]) -> Callable[[], None]:
        """Subscribe to an event type with async handler. Returns unsubscribe function."""
        if event_type not in self._async_subscribers:
            self._async_subscribers[event_type] = []
        
        self._async_subscribers[event_type].append(handler)
        
        def unsubscribe():
            if event_type in self._async_subscribers:
                try:
                    self._async_subscribers[event_type].remove(handler)
                except ValueError:
                    pass
        
        return unsubscribe
    
    def publish(self, event_type: str, properties: Dict[str, Any]) -> None:
        """Publish an event synchronously."""
        event = Event(type=event_type, properties=properties)
        
        # Call sync subscribers
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception:
                pass  # Ignore handler errors
    
    async def publish_async(self, event_type: str, properties: Dict[str, Any]) -> None:
        """Publish an event asynchronously."""
        event = Event(type=event_type, properties=properties)
        
        # Call sync subscribers
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception:
                pass
        
        # Call async subscribers
        tasks = []
        for handler in self._async_subscribers.get(event_type, []):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    tasks.append(result)
            except Exception:
                pass
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Global event bus instance
Bus = EventBus()


def event(name: str, schema: type[BaseModel]) -> str:
    """Create a typed event."""
    return name