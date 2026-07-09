# skills/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class SkillResult:
    success: bool
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

class Skill(ABC):
    """Base class for all skills"""
    
    name: str
    description: str
    
    @abstractmethod
    async def execute(self, **kwargs) -> SkillResult:
        """Execute the skill with given parameters"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop execution immediately"""
        pass
    
    @abstractmethod
    async def status(self) -> Dict[str, Any]:
        """Return current status"""
        pass
    
    def __init__(self):
        self._running = False
    
    @property
    def is_running(self) -> bool:
        return self._running