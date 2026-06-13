"""Task models for Tube Manager."""

import uuid
import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum

class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskPriority(str, Enum):
    """Task priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Task(BaseModel):
    """Task model."""
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    title: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    payload: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    updated_at: Optional[str] = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    result: Optional[str] = None
    error: Optional[str] = None