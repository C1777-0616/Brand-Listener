"""
OtherBrandCampaignAnalystAgent - analyzes competitor brand campaigns.

This agent is part of the 'analyst' group in the LangGraph architecture.
It consumes BrandCultureEvents and SocialMediaFeedback from the searcher group,
plus CompetitionData from state, and produces CompetitorCampaignAnalysis.
"""
import logging
import random
from typing import Dict, Any, List
from datetime import datetime

from ...data_models.analyst_results import (
    CompetitorCampaignAnalysis, CampaignComparison
)

logger = logging.getLogger(__name__)


class OtherBrandCampaignAnalystAgent:
    """Agent that analyzes competitor brand campaigns."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.use_mock = config.get("use_mock", True)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            competition_data = state.get("CompetitionData", [])
            brand_culture = state.get("BrandCultureEvents")
            social_feedback = state.get("SocialMediaFeedback")

            analysis = self._analyze(competition_data, brand_culture, social_feedback)

            logger.info(f"OtherBrandCampaignAnalystAgent completed: analyzed {len(analysis.competitors)} competitors")
            return {"CompetitorCampaignAnalysis": analysis.to_dict()}

        except Exception as e:
            logger.error(f"OtherBrandCampaignAnalystAgent failed: {e}", exc_info=True)
            return {"CompetitorCampaignAnalysis": CompetitorCampaignAnalysis().to_dict()}

    def _analyze(self, competition_data: Any, brand_culture: Any, social_feedback: Any) -> CompetitorCampaignAnalysis:
        if self.use_mock:
            return self._generate_mock_analysis()
        return CompetitorCampaignAnalysis()

    def _generate_mock_analysis(self) -> CompetitorCampaignAnalysis:
        competitors = ["竞品A", "竞品B", "竞品C"]
        campaigns = []

        campaign_templates = [
            ("618大促活动", "promotion", "年中大促，全品类折扣"),
            ("新品发布会", "launch", "旗舰新品线上发布"),
            ("品牌联名企划", "event", "与知名IP联名合作"),
            ("双十一预热", "promotion", "双十一预售活动"),
            ("用户回馈季", "event", "会员专享回馈活动"),
        ]

        for i, competitor in enumerate(competitors):
            for name, ctype, desc in random.sample(campaign_templates, k=random.randint(1, 2)):
                reach = random.randint(100000, 5000000)
                engagement = round(random.uniform(0.01, 0.15), 4)
                campaigns.append(CampaignComparison(
                    competitor_name=competitor,
                    campaign_name=name,
                    campaign_type=ctype,
                    platforms=random.sample(["微博", "抖音", "小红书", "B站", "微信"], k=random.randint(1, 3)),
                    estimated_reach=reach,
                    engagement_rate=engagement,
                    sentiment_score=round(random.uniform(0.3, 0.9), 2),
                    key_messages=[f"核心信息{j}" for j in range(1, random.randint(2, 4))],
                    effectiveness_score=round(random.uniform(0.3, 0.95), 2),
                ))

        insights = [
            f"{competitors[0]}在社交媒体的投放力度最大，互动率领先",
            f"{competitors[1]}侧重性价比路线，用户口碑较好",
            f"{competitors[2]}在联名营销方面表现突出",
            "行业整体向短视频和直播带货倾斜",
        ]

        recommendation = (
            f"建议关注{competitors[0]}的投放策略和{competitors[1]}的口碑运营方法。"
            "可参考竞品在短视频平台的内容形式，同时强化自身品牌差异化定位。"
        )

        return CompetitorCampaignAnalysis(
            competitors=competitors,
            campaigns=campaigns,
            total_campaigns_analyzed=len(campaigns),
            market_insights=insights,
            recommendation=recommendation,
        )


def create_other_brand_campaign_analyst_agent(config: Dict[str, Any]):
    agent = OtherBrandCampaignAnalystAgent(config)
    def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        return agent.invoke(state)
    return agent_node


DEFAULT_CONFIG = {
    "use_mock": True,
}


if __name__ == "__main__":
    agent = OtherBrandCampaignAnalystAgent({"use_mock": True})
    result = agent.invoke({})
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
