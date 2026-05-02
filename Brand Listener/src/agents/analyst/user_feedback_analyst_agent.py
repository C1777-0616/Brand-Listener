"""
UserFeedbackAnalystAgent - analyzes user feedback from social and shopping platforms.

This agent is part of the 'analyst' group in the LangGraph architecture.
It consumes ShoppingFeedback and SocialMediaFeedback from the searcher group
and produces UserFeedbackInsights.
"""
import logging
import random
from typing import Dict, Any, List
from datetime import datetime

from ...data_models.analyst_results import (
    UserFeedbackInsights, FeedbackTrend, PainPoint, Sentiment
)

logger = logging.getLogger(__name__)


class UserFeedbackAnalystAgent:
    """Agent that analyzes user feedback data to extract insights."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.use_mock = config.get("use_mock", True)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            shopping_feedback = state.get("ShoppingFeedback")
            social_feedback = state.get("SocialMediaFeedback")

            insights = self._analyze(shopping_feedback, social_feedback)

            logger.info(f"UserFeedbackAnalystAgent completed: {len(insights.trends)} trends, {len(insights.pain_points)} pain points")
            return {"UserFeedbackInsights": insights.to_dict()}

        except Exception as e:
            logger.error(f"UserFeedbackAnalystAgent failed: {e}", exc_info=True)
            return {"UserFeedbackInsights": UserFeedbackInsights().to_dict()}

    def _analyze(self, shopping_feedback: Any, social_feedback: Any) -> UserFeedbackInsights:
        if self.use_mock:
            return self._generate_mock_insights()
        return UserFeedbackInsights()

    def _generate_mock_insights(self) -> UserFeedbackInsights:
        trends = [
            FeedbackTrend(
                trend_name="品质关注度提升",
                description="用户对产品品质的关注度持续上升，高品质评价占比增加",
                sentiment=Sentiment.POSITIVE,
                frequency=random.randint(100, 500),
                platforms=random.sample(["淘宝", "京东", "微博", "小红书"], k=random.randint(2, 4)),
                sample_feedback=["品质超出预期", "做工精细，用料扎实", "这个价位品质很不错"],
            ),
            FeedbackTrend(
                trend_name="物流时效抱怨",
                description="部分区域物流时效不达预期，偏远地区尤为明显",
                sentiment=Sentiment.NEGATIVE,
                frequency=random.randint(50, 300),
                platforms=random.sample(["淘宝", "京东", "拼多多"], k=random.randint(2, 3)),
                sample_feedback=["等了整整一周才到", "物流太慢了", "配送时间比预计晚了两天"],
            ),
            FeedbackTrend(
                trend_name="包装设计好评",
                description="新包装设计获得较多正面反馈，尤其是送礼场景",
                sentiment=Sentiment.POSITIVE,
                frequency=random.randint(30, 200),
                platforms=random.sample(["小红书", "微博", "淘宝"], k=random.randint(1, 3)),
                sample_feedback=["包装太精美了", "送礼很有面子", "设计感满满"],
            ),
            FeedbackTrend(
                trend_name="客服响应期待",
                description="用户对客服响应速度和服务质量有更高期待",
                sentiment=Sentiment.NEUTRAL,
                frequency=random.randint(40, 250),
                platforms=random.sample(["微博", "淘宝", "京东"], k=random.randint(2, 3)),
                sample_feedback=["客服回复有点慢", "希望有24小时客服", "售后处理流程需要优化"],
            ),
        ]

        pain_points = [
            PainPoint(
                issue="配送时效不稳定",
                severity=8,
                frequency=random.randint(80, 400),
                affected_aspect="物流配送",
                suggested_improvement="优化仓储布局，增加前置仓覆盖",
            ),
            PainPoint(
                issue="部分尺码缺货",
                severity=6,
                frequency=random.randint(50, 300),
                affected_aspect="库存管理",
                suggested_improvement="基于销售数据优化库存预测和补货策略",
            ),
            PainPoint(
                issue="售后服务流程繁琐",
                severity=7,
                frequency=random.randint(60, 350),
                affected_aspect="售后服务",
                suggested_improvement="简化退换货流程，引入自助售后系统",
            ),
        ]

        return UserFeedbackInsights(
            trends=trends,
            pain_points=pain_points,
            overall_sentiment=Sentiment.NEUTRAL,
            summary=(
                f"用户反馈分析完成：发现 {len(trends)} 个主要趋势和 {len(pain_points)} 个核心痛点。"
                "品质和包装获得好评，物流和售后是主要改进方向。"
            ),
        )


def create_user_feedback_analyst_agent(config: Dict[str, Any]):
    agent = UserFeedbackAnalystAgent(config)
    def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        return agent.invoke(state)
    return agent_node


DEFAULT_CONFIG = {
    "use_mock": True,
}


if __name__ == "__main__":
    agent = UserFeedbackAnalystAgent({"use_mock": True})
    result = agent.invoke({})
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
