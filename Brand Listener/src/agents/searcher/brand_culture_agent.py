"""
BrandCultureListeningAgent - monitors brand culture discussions across platforms.

This agent is part of the 'searcher' group in the LangGraph architecture.
It collects brand culture events and generates cultural summaries.
"""
import logging
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ...data_models.brand_culture import (
    BrandCultureEvent, CultureSummary, Sentiment, EventCategory
)

logger = logging.getLogger(__name__)


class BrandCultureListeningAgent:
    """Agent that monitors brand culture-related discussions."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_sources = config.get("max_sources", 50)
        self.lookback_hours = config.get("lookback_hours", 24)
        self.use_mock = config.get("use_mock", True)
        self.last_run_time = None

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            brand_id, sources, frequency = self._extract_inputs(state)
            if not brand_id:
                logger.warning("No brandId provided to BrandCultureListeningAgent")
                return {"BrandCultureEvents": CultureSummary(brand_id="unknown", period_start=datetime.now(), period_end=datetime.now()).to_dict()}

            since = self._determine_since_time()
            events = self._collect_events(brand_id, sources, frequency, since)
            summary = self._generate_summary(brand_id, events, since)

            self.last_run_time = datetime.now()
            logger.info(f"BrandCultureListeningAgent processed brand {brand_id}, found {len(events)} events")
            return {"BrandCultureEvents": summary.to_dict()}

        except Exception as e:
            logger.error(f"BrandCultureListeningAgent failed: {e}", exc_info=True)
            return {"BrandCultureEvents": CultureSummary(brand_id="unknown", period_start=datetime.now(), period_end=datetime.now()).to_dict()}

    def _extract_inputs(self, state: Dict[str, Any]) -> tuple:
        brand_id = state.get("brandId") or state.get("brand_id") or ""
        sources = state.get("sources", [])
        if isinstance(sources, str):
            sources = [sources]
        elif not isinstance(sources, list):
            sources = []
        frequency = state.get("frequency", "daily")
        return brand_id, sources, frequency

    def _determine_since_time(self) -> datetime:
        if self.last_run_time:
            since = self.last_run_time
        else:
            since = datetime.now() - timedelta(hours=self.lookback_hours)
        max_lookback = datetime.now() - timedelta(hours=self.lookback_hours)
        if since < max_lookback:
            since = max_lookback
        return since

    def _collect_events(self, brand_id: str, sources: List[str], frequency: str, since: datetime) -> List[BrandCultureEvent]:
        if self.use_mock:
            return self._generate_mock_events(brand_id, sources, since)
        return []

    def _generate_mock_events(self, brand_id: str, sources: List[str], since: datetime) -> List[BrandCultureEvent]:
        platforms = ["weibo", "xiaohongshu", "bilibili", "douyin", "wechat"]
        categories = list(EventCategory)
        sentiments = list(Sentiment)

        topics = [
            "品牌联名讨论", "用户口碑分享", "新品发布讨论", "品牌价值观热议",
            "包装设计评价", "广告创意分析", "品牌活动参与", "用户体验分享",
            "行业趋势讨论", "品牌社会责任"
        ]

        events = []
        for i in range(random.randint(2, 5)):
            platform = random.choice(platforms)
            category = random.choice(categories)
            topic = random.choice(topics)
            published_at = datetime.now() - timedelta(hours=random.randint(0, 23))
            if published_at < since:
                continue

            event = BrandCultureEvent(
                id=f"culture_{brand_id}_{i}_{int(datetime.now().timestamp())}",
                brand_id=brand_id,
                platform=platform,
                content=f"【{topic}】关于品牌 {brand_id} 的{category.value}讨论在{platform}平台活跃，"
                        f"用户参与度高，讨论内容涉及品牌文化多个维度。",
                sentiment=random.choice(sentiments),
                category=category,
                source_url=f"https://{platform}.com/search?q={brand_id}",
                mention_count=random.randint(100, 50000),
                engagement_count=random.randint(500, 100000),
                keywords=random.sample(["国潮", "品质", "设计", "口碑", "创新", "性价比", "联名", "限量"], k=random.randint(2, 4)),
                timestamp=published_at,
            )
            events.append(event)

        return events

    def _generate_summary(self, brand_id: str, events: List[BrandCultureEvent], since: datetime) -> CultureSummary:
        category_dist = {}
        sentiment_dist = {"positive": 0, "neutral": 0, "negative": 0}
        all_keywords = set()

        for event in events:
            category_dist[event.category.value] = category_dist.get(event.category.value, 0) + 1
            sentiment_dist[event.sentiment.value] = sentiment_dist.get(event.sentiment.value, 0) + 1
            all_keywords.update(event.keywords)

        summary_text = f"品牌 {brand_id} 文化监听摘要：共发现 {len(events)} 个文化事件。"
        if category_dist:
            top_cat = max(category_dist, key=category_dist.get)
            summary_text += f"主要话题类别为「{top_cat}」。"
        if sentiment_dist.get("positive", 0) > sentiment_dist.get("negative", 0):
            summary_text += "整体舆论偏正面。"

        return CultureSummary(
            brand_id=brand_id,
            period_start=since,
            period_end=datetime.now(),
            total_events=len(events),
            dominant_categories=category_dist,
            sentiment_distribution=sentiment_dist,
            top_keywords=sorted(list(all_keywords))[:10],
            summary_text=summary_text,
            events=events,
        )


def create_brand_culture_agent(config: Dict[str, Any]):
    agent = BrandCultureListeningAgent(config)
    def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        return agent.invoke(state)
    return agent_node


DEFAULT_CONFIG = {
    "max_sources": 50,
    "lookback_hours": 24,
    "use_mock": True,
}


if __name__ == "__main__":
    agent = BrandCultureListeningAgent({"use_mock": True})
    result = agent.invoke({"brandId": "test_brand", "sources": ["https://weibo.com/brand"], "frequency": "daily"})
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
