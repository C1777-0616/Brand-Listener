"""
TaskDispatcherAgent - dispatches tasks to agent groups based on priorities.

This agent is part of the 'supervisor' group in the LangGraph architecture.
It manages task assignments and resource allocation.
"""
import logging
import random
import uuid
from typing import Dict, Any, List
from datetime import datetime, timedelta

from ...data_models.supervisor_models import (
    AssignmentPlan, TaskAssignment, TaskPriority, Task, TaskStatus
)

logger = logging.getLogger(__name__)


class TaskDispatcherAgent:
    """Agent that dispatches and manages task assignments."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.use_mock = config.get("use_mock", True)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            pending_tasks = state.get("PendingTasks", [])
            resource_availability = state.get("ResourceAvailability", {})

            plan = self._dispatch(pending_tasks, resource_availability)

            logger.info(f"TaskDispatcherAgent completed: assigned {plan.total_tasks} tasks")
            return {"AssignmentPlan": plan.to_dict()}

        except Exception as e:
            logger.error(f"TaskDispatcherAgent failed: {e}", exc_info=True)
            return {"AssignmentPlan": AssignmentPlan().to_dict()}

    def _dispatch(self, pending_tasks: Any, resource_availability: Any) -> AssignmentPlan:
        if self.use_mock:
            return self._generate_mock_plan()
        return AssignmentPlan()

    def _generate_mock_plan(self) -> AssignmentPlan:
        agents = {
            "searcher": ["BrandCultureListeningAgent", "SocialMediaFeedbackAgent", "ShoppingPlatformFeedbackAgent"],
            "analyst": ["OtherBrandCampaignAnalystAgent", "UserFeedbackAnalystAgent"],
            "reporter": ["TemplateDrivenReportAgent"],
            "supervisor": ["TaskDispatcherAgent"],
        }

        priorities = [TaskPriority.HIGH, TaskPriority.MEDIUM, TaskPriority.LOW]

        tasks_to_assign = [
            ("采集品牌文化数据", "searcher", "BrandCultureListeningAgent"),
            ("采集社交媒体反馈", "searcher", "SocialMediaFeedbackAgent"),
            ("采集电商平台评价", "searcher", "ShoppingPlatformFeedbackAgent"),
            ("分析竞品活动", "analyst", "OtherBrandCampaignAnalystAgent"),
            ("分析用户反馈趋势", "analyst", "UserFeedbackAnalystAgent"),
            ("生成周报", "reporter", "TemplateDrivenReportAgent"),
        ]

        assignments = []
        high_count = 0
        now = datetime.now()

        for i, (task_name, group, agent_name) in enumerate(tasks_to_assign):
            priority = random.choice(priorities)
            if priority == TaskPriority.HIGH:
                high_count += 1

            start_offset = i * random.randint(15, 60)
            duration = random.randint(30, 120)

            assignments.append(TaskAssignment(
                task_id=str(uuid.uuid4())[:8],
                assigned_to=agent_name,
                priority=priority,
                estimated_start=now + timedelta(minutes=start_offset),
                estimated_end=now + timedelta(minutes=start_offset + duration),
            ))

        return AssignmentPlan(
            assignments=assignments,
            total_tasks=len(assignments),
            high_priority_count=high_count,
            available_resources=8,
            plan_summary=f"任务分派完成：共 {len(assignments)} 个任务，{high_count} 个高优先级任务，"
                         f"涉及 4 个 Agent 组、{len(set(a.assigned_to for a in assignments))} 个 Agent。",
        )


def create_task_dispatcher_agent(config: Dict[str, Any]):
    agent = TaskDispatcherAgent(config)
    def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        return agent.invoke(state)
    return agent_node


DEFAULT_CONFIG = {
    "use_mock": True,
}


if __name__ == "__main__":
    agent = TaskDispatcherAgent({"use_mock": True})
    result = agent.invoke({})
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
