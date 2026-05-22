"""
LangGraph workflow for Brand Listener multi-agent pipeline.

Pipeline: Searcher -> Analyst -> Reporter -> Supervisor
Each group contains multiple agents that process data sequentially.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from src.agents.searcher.official_updates_agent import create_official_updates_agent
from src.agents.searcher.content_classification_agent import create_content_classification_agent
from src.agents.searcher.content_tagging_agent import create_content_tagging_agent
from src.agents.searcher.ocr_agent import create_ocr_agent
from src.agents.searcher.brand_culture_agent import create_brand_culture_agent
from src.agents.searcher.social_media_feedback_agent import create_social_media_feedback_agent
from src.agents.searcher.shopping_platform_feedback_agent import create_shopping_platform_feedback_agent
from src.agents.analyst.other_brand_campaign_analyst_agent import create_other_brand_campaign_analyst_agent
from src.agents.analyst.user_feedback_analyst_agent import create_user_feedback_analyst_agent
from src.agents.reporter.template_driven_report_agent import create_template_driven_report_agent
from src.agents.supervisor.task_dispatcher_agent import create_task_dispatcher_agent
from src.utils.config import (
    get_official_updates_agent_config, get_mock_folo_config,
    get_brand_culture_agent_config, get_social_media_feedback_agent_config,
    get_shopping_platform_feedback_agent_config,
    get_other_brand_campaign_analyst_agent_config,
    get_user_feedback_analyst_agent_config,
    get_template_driven_report_agent_config,
    get_task_dispatcher_agent_config,
    get_xhs_agent_config,
    get_ocr_agent_config,
)


# ── State Definition ──

class AgentState(TypedDict):
    """Full state for the multi-agent LangGraph pipeline."""

    # Pipeline control
    run_searchers: bool
    run_analysts: bool
    run_reporter: bool
    run_supervisor: bool

    # Input
    brandId: Optional[str]
    sources: List[str]
    platforms: List[str]
    frequency: Optional[str]

    # ── Searcher outputs ──
    OfficialUpdates: Optional[Dict[str, Any]]
    BrandCultureEvents: Optional[Dict[str, Any]]
    SocialMediaFeedback: Optional[Dict[str, Any]]
    ShoppingFeedback: Optional[Dict[str, Any]]

    # ── Analyst outputs ──
    CompetitorCampaignAnalysis: Optional[Dict[str, Any]]
    UserFeedbackInsights: Optional[Dict[str, Any]]

    # ── Reporter outputs ──
    Reports: Optional[Dict[str, Any]]

    # ── Supervisor outputs ──
    AssignmentPlan: Optional[Dict[str, Any]]


# ── Factory function for full pipeline ──

def create_full_workflow(use_mock: bool = True) -> StateGraph:
    """
    Create the complete multi-agent LangGraph pipeline.
    """

    ofu_config = get_official_updates_agent_config() if not use_mock else {
        **get_official_updates_agent_config(),
        "folo_config": get_mock_folo_config(),
    }
    # 合并小红书配置到 OfficialUpdatesAgent config
    ofu_config.update(get_xhs_agent_config())
    bcl_config = get_brand_culture_agent_config()
    smf_config = get_social_media_feedback_agent_config()
    spf_config = get_shopping_platform_feedback_agent_config()
    obc_config = get_other_brand_campaign_analyst_agent_config()
    ufa_config = get_user_feedback_analyst_agent_config()
    tdr_config = get_template_driven_report_agent_config()
    tda_config = get_task_dispatcher_agent_config()

    # Create agent nodes
    official_updates_node = create_official_updates_agent(ofu_config)
    content_classification_node = create_content_classification_agent({})
    content_tagging_node = create_content_tagging_agent({})
    ocr_node = create_ocr_agent(get_ocr_agent_config())
    brand_culture_node = create_brand_culture_agent(bcl_config)
    social_feedback_node = create_social_media_feedback_agent(smf_config)
    shopping_feedback_node = create_shopping_platform_feedback_agent(spf_config)
    campaign_analyst_node = create_other_brand_campaign_analyst_agent(obc_config)
    feedback_analyst_node = create_user_feedback_analyst_agent(ufa_config)
    report_node = create_template_driven_report_agent(tdr_config)
    dispatcher_node = create_task_dispatcher_agent(tda_config)

    # Build graph
    workflow = StateGraph(AgentState)

    # Add all nodes
    workflow.add_node("official_updates_agent", official_updates_node)
    workflow.add_node("content_classification_agent", content_classification_node)
    workflow.add_node("content_tagging_agent", content_tagging_node)
    workflow.add_node("ocr_agent", ocr_node)
    workflow.add_node("brand_culture_agent", brand_culture_node)
    workflow.add_node("social_media_feedback_agent", social_feedback_node)
    workflow.add_node("shopping_platform_feedback_agent", shopping_feedback_node)
    workflow.add_node("campaign_analyst_agent", campaign_analyst_node)
    workflow.add_node("feedback_analyst_agent", feedback_analyst_node)
    workflow.add_node("report_agent", report_node)
    workflow.add_node("dispatcher_agent", dispatcher_node)

    # Set entry point
    workflow.set_entry_point("official_updates_agent")

    # ── Searcher group edges (sequential) ──
    workflow.add_edge("official_updates_agent", "content_classification_agent")
    workflow.add_edge("content_classification_agent", "content_tagging_agent")

    # 跳过 OCR / mock agent / analyst / reporter / dispatcher
    # 只跑：官方更新(FOLO+小红书博主) → 分类 → 打标
    workflow.add_edge("content_tagging_agent", END)

    return workflow.compile()


# ── Convenience runners ──

def run_full_pipeline(
    sources: List[str] = None,
    brand_id: str = "test_brand",
    platforms: List[str] = None,
    use_mock: bool = True,
) -> Dict[str, Any]:
    """Run the complete multi-agent pipeline."""
    if sources is None:
        sources = [
            "https://weibo.com/officialbrand",
            "https://xiaohongshu.com/user/brand",
            "https://douyin.com/user/brand",
        ]
    if platforms is None:
        platforms = ["taobao", "jd", "pinduoduo"]

    app = create_full_workflow(use_mock)

    initial_state: AgentState = {
        "run_searchers": True,
        "run_analysts": True,
        "run_reporter": True,
        "run_supervisor": True,
        "brandId": brand_id,
        "sources": sources,
        "platforms": platforms,
        "frequency": "daily",
        "OfficialUpdates": None,
        "BrandCultureEvents": None,
        "SocialMediaFeedback": None,
        "ShoppingFeedback": None,
        "CompetitorCampaignAnalysis": None,
        "UserFeedbackInsights": None,
        "Reports": None,
        "AssignmentPlan": None,
    }

    result = app.invoke(initial_state)
    return result


# ── Result printer ──

def print_pipeline_result(result: Dict[str, Any]) -> None:
    """Print pipeline results in a readable format."""
    print("=" * 80)
    print("BRAND LISTENER - FULL PIPELINE RESULT")
    print("=" * 80)

    # Searcher results
    print("\n[SEARCHER GROUP]")
    ofu = result.get("OfficialUpdates")
    if ofu:
        updates = ofu.get("updates", [])
        print(f"  OfficialUpdatesAgent: {len(updates)} updates from {ofu.get('source_count', 0)} sources")

    bce = result.get("BrandCultureEvents")
    if bce:
        events = bce.get("events", [])
        print(f"  BrandCultureListeningAgent: {bce.get('total_events', len(events))} events, "
              f"sentiment: {bce.get('sentiment_distribution', {})}")

    smf = result.get("SocialMediaFeedback")
    if smf:
        print(f"  SocialMediaFeedbackAgent: {len(smf.get('items', []))} items from {smf.get('source_count', 0)} sources")

    spf = result.get("ShoppingFeedback")
    if spf:
        print(f"  ShoppingPlatformFeedbackAgent: {len(spf.get('items', []))} items from {spf.get('platform_count', 0)} platforms")

    # Analyst results
    print("\n[ANALYST GROUP]")
    cca = result.get("CompetitorCampaignAnalysis")
    if cca:
        print(f"  CampaignAnalystAgent: {cca.get('total_campaigns_analyzed', 0)} campaigns from {len(cca.get('competitors', []))} competitors")
        print(f"  Recommendation: {cca.get('recommendation', 'N/A')[:80]}...")

    ufi = result.get("UserFeedbackInsights")
    if ufi:
        print(f"  FeedbackAnalystAgent: {len(ufi.get('trends', []))} trends, {len(ufi.get('pain_points', []))} pain points")
        print(f"  Overall: {ufi.get('overall_sentiment', 'N/A')}")

    # Reporter results
    print("\n[REPORTER GROUP]")
    rpt = result.get("Reports")
    if rpt:
        report = rpt.get("report", {})
        print(f"  TemplateDrivenReportAgent: '{report.get('title', 'N/A')}' ({report.get('template', 'N/A')})")
        print(f"  Markdown length: {len(rpt.get('markdown', ''))} chars")

    # Supervisor results
    print("\n[SUPERVISOR GROUP]")
    plan = result.get("AssignmentPlan")
    if plan:
        print(f"  TaskDispatcherAgent: {plan.get('total_tasks', 0)} tasks, "
              f"{plan.get('high_priority_count', 0)} high priority")
        print(f"  Summary: {plan.get('plan_summary', 'N/A')}")

    print("\n" + "=" * 80)


# ── Main entry point ──

if __name__ == "__main__":
    print("Running Brand Listener full pipeline with mock data...\n")
    result = run_full_pipeline(use_mock=True)
    print_pipeline_result(result)
