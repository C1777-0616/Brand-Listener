"""
报告生成器：封装 BettaFish ReportAgent，提供简化的调用接口。

职责：
- 初始化 ReportAgent（使用 .env 中的 LLM 配置）
- 将 entries_store 数据转换为 ReportAgent 所需格式
- 管理生成任务的状态和进度
"""

import json
import os
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# 将 BettaFish 加入 sys.path
_root = Path(__file__).parent.parent.parent  # Brand Listener/Brand Listener/
_bettafish = _root.parent / "BettaFish"  # Brand Listener/BettaFish/
if str(_bettafish) not in sys.path:
    sys.path.insert(0, str(_bettafish))

from .data_converter import convert_entries_to_reports


class ReportTask:
    """单个报告生成任务的状态。"""

    def __init__(self, task_id: str, query: str, days: int):
        self.task_id = task_id
        self.query = query
        self.days = days
        self.status = "pending"  # pending / running / completed / failed
        self.progress = 0
        self.message = ""
        self.html_content: Optional[str] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None
        self.report_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "query": self.query,
            "days": self.days,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "report_id": self.report_id,
        }


class ReportGenerator:
    """报告生成器，管理 ReportAgent 实例和任务队列。"""

    def __init__(self):
        self._agent = None
        self._agent_error: Optional[str] = None
        self._tasks: Dict[str, ReportTask] = {}
        self._lock = threading.Lock()

    def _ensure_agent(self) -> bool:
        """懒加载初始化 ReportAgent。"""
        if self._agent is not None:
            return True
        if self._agent_error:
            return False
        try:
            # 设置 BettaFish 所需的工作目录
            bettafish_dir = str(_bettafish)
            original_cwd = os.getcwd()
            os.chdir(bettafish_dir)
            try:
                from ReportEngine.agent import create_agent
                self._agent = create_agent()
            finally:
                os.chdir(original_cwd)
            return True
        except Exception as e:
            self._agent_error = str(e)
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取报告引擎状态。"""
        ready = self._ensure_agent()
        return {
            "ready": ready,
            "error": self._agent_error,
            "active_tasks": len([t for t in self._tasks.values() if t.status == "running"]),
            "total_tasks": len(self._tasks),
        }

    def get_templates(self) -> List[Dict[str, str]]:
        """获取可用的报告模板列表。"""
        template_dir = _bettafish / "ReportEngine" / "report_template"
        templates = []
        if template_dir.exists():
            for f in sorted(template_dir.glob("*.md")):
                name = f.stem
                templates.append({"name": name, "filename": f.name})
        # 添加自定义模板
        custom_dir = _root / "report_templates"
        if custom_dir.exists():
            for f in sorted(custom_dir.glob("*.md")):
                name = f.stem
                templates.append({"name": f"[自定义] {name}", "filename": f.name, "custom": True})
        return templates

    def start_report(
        self,
        entries_store: Dict[str, Any],
        query: str = "口腔护理行业品牌监测报告",
        days: int = 30,
        template_name: Optional[str] = None,
    ) -> str:
        """启动报告生成任务，返回 task_id。"""
        if not self._ensure_agent():
            raise RuntimeError(f"报告引擎初始化失败: {self._agent_error}")

        task_id = f"rpt-{uuid.uuid4().hex[:8]}"
        task = ReportTask(task_id, query, days)

        with self._lock:
            self._tasks[task_id] = task

        # 在后台线程运行
        thread = threading.Thread(
            target=self._run_generation,
            args=(task, entries_store, template_name),
            daemon=True,
            name=f"report-{task_id}",
        )
        thread.start()
        return task_id

    def _run_generation(
        self,
        task: ReportTask,
        entries_store: Dict[str, Any],
        template_name: Optional[str],
    ):
        """后台执行报告生成。"""
        task.status = "running"
        task.progress = 5
        task.message = "正在转换数据..."

        try:
            # 数据转换
            report_query, report_media, report_insight = convert_entries_to_reports(
                entries_store, task.days
            )
            task.progress = 15
            task.message = "数据转换完成，正在调用 LLM 生成报告..."

            # 流式回调：更新进度
            def stream_handler(event_type: str, payload: Dict[str, Any]):
                if event_type == "progress":
                    pct = payload.get("progress", 0)
                    # 映射到 15-95 区间
                    task.progress = min(15 + int(pct * 0.8), 95)
                    task.message = payload.get("message", "生成中...")
                elif event_type == "chapter_status":
                    ch_title = payload.get("title", "")
                    ch_status = payload.get("status", "")
                    if ch_status == "completed":
                        task.message = f"章节完成: {ch_title}"
                    elif ch_status == "running":
                        task.message = f"正在生成: {ch_title}"

            # 加载自定义模板
            custom_template = ""
            if template_name:
                custom_template = self._load_template(template_name)

            # 调用 ReportAgent
            bettafish_dir = str(_bettafish)
            original_cwd = os.getcwd()
            os.chdir(bettafish_dir)
            try:
                result = self._agent.generate_report(
                    query=task.query,
                    reports=[report_query, report_media, report_insight],
                    forum_logs="",
                    custom_template=custom_template,
                    save_report=True,
                    stream_handler=stream_handler,
                )
            finally:
                os.chdir(original_cwd)

            task.status = "completed"
            task.progress = 100
            task.message = "报告生成完成"
            task.html_content = result.get("html_content", "")
            task.report_id = result.get("report_id", "")
            task.completed_at = datetime.now().isoformat()

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.message = f"生成失败: {e}"
            task.completed_at = datetime.now().isoformat()

    def _load_template(self, template_name: str) -> str:
        """加载模板文件内容。"""
        # 先查自定义模板
        custom_dir = _root / "report_templates"
        custom_path = custom_dir / template_name
        if custom_path.exists():
            return custom_path.read_text(encoding="utf-8")
        # 查 BettaFish 模板
        template_dir = _bettafish / "ReportEngine" / "report_template"
        template_path = template_dir / template_name
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        # 按名称匹配
        for d in [custom_dir, template_dir]:
            if d.exists():
                for f in d.glob("*.md"):
                    if f.stem == template_name or f.name == template_name:
                        return f.read_text(encoding="utf-8")
        return ""

    def get_task(self, task_id: str) -> Optional[ReportTask]:
        """获取任务状态。"""
        return self._tasks.get(task_id)

    def get_task_html(self, task_id: str) -> Optional[str]:
        """获取任务的 HTML 报告内容。"""
        task = self._tasks.get(task_id)
        if task and task.status == "completed":
            return task.html_content
        return None

    def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有任务。"""
        return [t.to_dict() for t in self._tasks.values()]


# 全局单例
_report_generator: Optional[ReportGenerator] = None
_init_lock = threading.Lock()


def get_report_generator() -> ReportGenerator:
    """获取报告生成器单例。"""
    global _report_generator
    if _report_generator is None:
        with _init_lock:
            if _report_generator is None:
                _report_generator = ReportGenerator()
    return _report_generator
