# core/events.py
from typing import Callable, Any, Dict, List
from dataclasses import dataclass
from datetime import datetime
import asyncio

@dataclass
class Event:
    """Base event class"""
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = None
    source: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class EventBus:
    """Central event pub/sub system"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to event type"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    async def publish(self, event: Event):
        """Publish event to all subscribers"""
        if event.event_type in self._subscribers:
            tasks = [
                handler(event) 
                for handler in self._subscribers[event.event_type]
            ]
            await asyncio.gather(*tasks)
    
    def unsubscribe(self, event_type: str, handler: Callable):
        """Unsubscribe from event type"""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)

# Global event bus
event_bus = EventBus()

# Standard event types
class EventTypes:
    # Voice events
    VOICE_WAKE_WORD_DETECTED = "voice.wake_word_detected"
    VOICE_TRANSCRIBED = "voice.transcribed"
    VOICE_COMMAND_RECOGNIZED = "voice.command_recognized"
    
    # Memory events
    MEMORY_STORED = "memory.stored"
    MEMORY_RETRIEVED = "memory.retrieved"
    
    # Navigation events
    NAVIGATION_STARTED = "navigation.started"
    NAVIGATION_COMPLETED = "navigation.completed"
    NAVIGATION_OBSTACLE = "navigation.obstacle"
    
    # Skill events
    SKILL_EXECUTED = "skill.executed"
    SKILL_FAILED = "skill.failed"
    
    # System events
    SYSTEM_ERROR = "system.error"
    SYSTEM_SHUTDOWN = "system.shutdown"