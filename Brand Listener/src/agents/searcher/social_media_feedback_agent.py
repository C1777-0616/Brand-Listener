"""
SocialMediaFeedbackAgent - collects user feedback from social media platforms.

This agent is part of the 'searcher' group in the LangGraph architecture.
It aggregates feedback items from social media sources.
"""
import logging
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ...data_models.social_feedback import (
    SocialMediaFeedback, SocialFeedbackItem, Sentiment, FeedbackPlatform
)

logger = logging.getLogger(__name__)


class SocialMediaFeedbackAgent:
    """Agent that collects social media user feedback."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_sources = config.get("max_sources", 50)
        self.lookback_hours = config.get("lookback_hours", 24)
        self.use_mock = config.get("use_mock", True)
        self.last_run_time = None
        self.processed_ids = set()

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            sources = self._extract_sources(state)
            if not sources:
                logger.warning("No sources provided to SocialMediaFeedbackAgent")
                return {"SocialMediaFeedback": SocialMediaFeedback().to_dict()}

            since = self._determine_since_time()
            feedback_items = self._collect_feedback(sources, since)
            result = self._build_result(feedback_items, sources)

            self.last_run_time = datetime.now()
            logger.info(f"SocialMediaFeedbackAgent processed {len(sources)} sources, found {len(feedback_items)} items")
            return {"SocialMediaFeedback": result.to_dict()}

        except Exception as e:
            logger.error(f"SocialMediaFeedbackAgent failed: {e}", exc_info=True)
            return {"SocialMediaFeedback": SocialMediaFeedback().to_dict()}

    def _extract_sources(self, state: Dict[str, Any]) -> List[str]:
        sources = state.get("sources", [])
        if isinstance(sources, str):
            sources = [sources]
        elif not isinstance(sources, list):
            sources = []
        valid = [s for s in sources if isinstance(s, str) and s.startswith(("http://", "https://"))]
        return valid

    def _determine_since_time(self) -> datetime:
        if self.last_run_time:
            since = self.last_run_time
        else:
            since = datetime.now() - timedelta(hours=self.lookback_hours)
        max_lookback = datetime.now() - timedelta(hours=self.lookback_hours)
        if since < max_lookback:
            since = max_lookback
        return since

    def _collect_feedback(self, sources: List[str], since: datetime) -> List[SocialFeedbackItem]:
        if self.use_mock:
            return self._generate_mock_feedback(sources, since)
        return []

    def _generate_mock_feedback(self, sources: List[str], since: datetime) -> List[SocialFeedbackItem]:
        platforms = list(FeedbackPlatform)
        sentiments = list(Sentiment)
        feedback_templates = [
            "产品使用体验很好，推荐给大家！",
            "物流速度有点慢，希望能改进。",
            "新款设计很时尚，已经下单了。",
            "客服态度很好，问题解决了。",
            "价格略高，但品质对得起这个价位。",
            "包装很精美，送礼很有面子。",
            "用了两周了，效果超出预期。",
            "有些细节还需要改进，整体还不错。",
            "第二次购买了，品质稳定。",
            "朋友推荐的，果然没失望。",
        ]

        items = []
        for source in sources:
            for i in range(random.randint(2, 4)):
                published_at = datetime.now() - timedelta(hours=random.randint(0, 23))
                if published_at < since:
                    continue

                platform = random.choice(platforms)
                fb_id = f"social_{platform.value}_{i}_{int(datetime.now().timestamp())}"
                if fb_id in self.processed_ids:
                    continue
                self.processed_ids.add(fb_id)

                item = SocialFeedbackItem(
                    id=fb_id,
                    platform=platform,
                    source_url=source,
                    content=random.choice(feedback_templates),
                    sentiment=random.choice(sentiments),
                    likes=random.randint(0, 5000),
                    comments=random.randint(0, 1000),
                    shares=random.randint(0, 500),
                    author_name=f"用户_{random.randint(1000, 9999)}",
                    is_influencer=random.random() < 0.1,
                    timestamp=published_at,
                )
                items.append(item)

        return items

    def _build_result(self, items: List[SocialFeedbackItem], sources: List[str]) -> SocialMediaFeedback:
        result = SocialMediaFeedback(items=items)
        processed_sources = set(item.source_url for item in items)
        for source in sources:
            result.add_successful_source(source)
        return result


def create_social_media_feedback_agent(config: Dict[str, Any]):
    agent = SocialMediaFeedbackAgent(config)
    def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        return agent.invoke(state)
    return agent_node


DEFAULT_CONFIG = {
    "max_sources": 50,
    "lookback_hours": 24,
    "use_mock": True,
}


if __name__ == "__main__":
    agent = SocialMediaFeedbackAgent({"use_mock": True})
    result = agent.invoke({"sources": ["https://weibo.com/brand", "https://xiaohongshu.com/user/brand"]})
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
