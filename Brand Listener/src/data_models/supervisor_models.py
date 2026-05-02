"""
Data models for TaskDispatcherAgent output.
Aligns with contract defined in interfaces/agent_contracts.json.
"""
from enum import Enum
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class TaskPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique task identifier")
    name: str = Field(..., description="Task name")
    description: str = Field(default="", description="Task description")
    agent_group: str = Field(..., description="Target agent group (searcher/analyst/reporter)")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task priority")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current task status")
    depends_on: List[str] = Field(default_factory=list, description="Task IDs this task depends on")
    estimated_duration_minutes: int = Field(default=30, description="Estimated duration")
    created_at: datetime = Field(default_factory=datetime.now, description="When the task was created")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ResourceSlot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    agent_name: str = Field(..., description="Agent name")
    group: str = Field(..., description="Agent group")
    available: bool = Field(default=True, description="Whether the resource is available")
    current_load: int = Field(default=0, description="Current task load count")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class TaskAssignment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(..., description="Assigned task ID")
    assigned_to: str = Field(..., description="Agent assigned to the task")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Assigned priority")
    estimated_start: Optional[datetime] = Field(None, description="Estimated start time")
    estimated_end: Optional[datetime] = Field(None, description="Estimated end time")

    def to_dict(self) -> Dict[str, Any]:
        result = self.model_dump()
        if self.estimated_start:
            result["estimated_start"] = self.estimated_start.isoformat()
        if self.estimated_end:
            result["estimated_end"] = self.estimated_end.isoformat()
        return result


class AssignmentPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    assignments: List[TaskAssignment] = Field(default_factory=list, description="Task assignments")
    total_tasks: int = Field(0, description="Total tasks assigned")
    high_priority_count: int = Field(0, description="High priority task count")
    available_resources: int = Field(0, description="Available resource count")
    plan_summary: str = Field(default="", description="Execution plan summary")
    created_at: datetime = Field(default_factory=datetime.now, description="When the plan was created")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assignments": [a.to_dict() for a in self.assignments],
            "total_tasks": self.total_tasks,
            "high_priority_count": self.high_priority_count,
            "available_resources": self.available_resources,
            "plan_summary": self.plan_summary,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssignmentPlan":
        assignments = [TaskAssignment(**a) for a in data.get("assignments", [])]
        return cls(
            assignments=assignments,
            total_tasks=data.get("total_tasks", 0),
            high_priority_count=data.get("high_priority_count", 0),
            available_resources=data.get("available_resources", 0),
            plan_summary=data.get("plan_summary", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )
