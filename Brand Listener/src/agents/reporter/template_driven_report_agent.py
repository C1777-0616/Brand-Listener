"""
TemplateDrivenReportAgent - generates structured reports from analysis results.

This agent is part of the 'reporter' group in the LangGraph architecture.
It consumes analysis results and insights to produce reports in multiple formats.
"""
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

from ...data_models.report_models import (
    Report, ReportBundle, ReportSection, ReportTemplate
)

logger = logging.getLogger(__name__)


class TemplateDrivenReportAgent:
    """Agent that generates reports from analysis results."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.use_mock = config.get("use_mock", True)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            analysis_results = state.get("AnalysisResults", {})
            insights = state.get("Insights", {})
            selected_template = state.get("SelectedTemplate", "weekly_digest")

            bundle = self._generate_report(analysis_results, insights, selected_template)

            logger.info(f"TemplateDrivenReportAgent completed: report '{bundle.report.title}' generated")
            return {"Reports": bundle.to_dict()}

        except Exception as e:
            logger.error(f"TemplateDrivenReportAgent failed: {e}", exc_info=True)
            empty = ReportBundle(
                report=Report(id="error", title="Error Report", template=ReportTemplate.CUSTOM),
                markdown="",
                json_data="{}",
            )
            return {"Reports": empty.to_dict()}

    def _generate_report(self, analysis_results: Any, insights: Any, template_name: str) -> ReportBundle:
        if self.use_mock:
            return self._generate_mock_report(template_name)
        return ReportBundle(
            report=Report(id="empty", title="Empty Report", template=ReportTemplate.CUSTOM),
        )

    def _generate_mock_report(self, template_name: str) -> ReportBundle:
        try:
            template = ReportTemplate(template_name)
        except ValueError:
            template = ReportTemplate.CUSTOM

        report_id = f"report_{int(datetime.now().timestamp())}"
        report_title = template_name.replace("_", " ").title()

        sections = [
            ReportSection(
                title="执行摘要",
                content=(
                    "本报告基于多渠道数据采集与分析生成。\n\n"
                    "主要发现：\n"
                    "- 品牌社交声量较上周增长15%\n"
                    "- 用户整体情绪偏正面（正面68%，中性22%，负面10%）\n"
                    "- 竞品活动监测到3个主要营销campaign\n"
                    "- 物流配送是当前用户最关注的改进方向"
                ),
                data_ref="summary",
            ),
            ReportSection(
                title="品牌文化动态",
                content=(
                    "本周监测到以下品牌文化相关事件：\n\n"
                    "1. **热门话题**：品牌联名讨论在微博和小红书持续活跃\n"
                    "2. **用户口碑**：新产品线获得KOL积极评价\n"
                    "3. **舆论关注**：品牌社会责任话题引发广泛讨论\n\n"
                    "建议持续关注联名合作的用户反馈，把握话题热度。"
                ),
                data_ref="brand_culture",
            ),
            ReportSection(
                title="用户反馈分析",
                content=(
                    "社交媒体及电商平台用户反馈分析结果：\n\n"
                    "### 正面反馈\n"
                    "- 产品品质获认可，复购率稳定\n"
                    "- 包装设计升级获得好评\n\n"
                    "### 改进建议\n"
                    "- 物流时效需要进一步优化\n"
                    "- 售后服务流程可简化\n"
                    "- 部分尺码库存需要补充"
                ),
                data_ref="user_feedback",
            ),
            ReportSection(
                title="竞品活动分析",
                content=(
                    "监测到的主要竞品活动：\n\n"
                    "| 竞品 | 活动 | 效果评估 |\n"
                    "|------|------|--------|\n"
                    "| 竞品A | 618大促 | 高互动率 |\n"
                    "| 竞品B | 新品发布 | 口碑良好 |\n"
                    "| 竞品C | IP联名 | 话题性强 |\n\n"
                    "建议在保持自身定位的同时，参考竞品在短视频平台的内容策略。"
                ),
                data_ref="competitor_analysis",
            ),
        ]

        report = Report(
            id=report_id,
            title=report_title,
            template=template,
            sections=sections,
            data_summary={
                "data_sources": ["微博", "小红书", "淘宝", "京东", "抖音"],
                "time_range": "过去24小时",
                "total_events": 156,
                "feedback_items": 423,
            },
        )

        markdown_output = report.to_markdown()
        json_output = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)

        return ReportBundle(
            report=report,
            markdown=markdown_output,
            json_data=json_output,
        )


def create_template_driven_report_agent(config: Dict[str, Any]):
    agent = TemplateDrivenReportAgent(config)
    def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        return agent.invoke(state)
    return agent_node


DEFAULT_CONFIG = {
    "use_mock": True,
}


if __name__ == "__main__":
    agent = TemplateDrivenReportAgent({"use_mock": True})
    result = agent.invoke({"SelectedTemplate": "weekly_digest"})
    import json as j
    print(j.dumps(result, indent=2, ensure_ascii=False))
    print("\n--- MARKDOWN ---")
    print(result.get("Reports", {}).get("markdown", "")[:500])
