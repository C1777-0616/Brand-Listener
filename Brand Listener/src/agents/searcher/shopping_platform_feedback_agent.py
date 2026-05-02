"""
ShoppingPlatformFeedbackAgent - collects user feedback from e-commerce platforms.

This agent is part of the 'searcher' group in the LangGraph architecture.
It aggregates product reviews and ratings from shopping platforms.
"""
import logging
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ...data_models.shopping_feedback import (
    ShoppingFeedback, ShoppingFeedbackItem, Sentiment, ShoppingPlatform
)

logger = logging.getLogger(__name__)


class ShoppingPlatformFeedbackAgent:
    """Agent that collects shopping platform feedback and reviews."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.lookback_hours = config.get("lookback_hours", 24)
        self.use_mock = config.get("use_mock", True)
        self.last_run_time = None
        self.processed_ids = set()

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            platforms = self._extract_platforms(state)
            if not platforms:
                logger.warning("No platforms provided to ShoppingPlatformFeedbackAgent")
                return {"ShoppingFeedback": ShoppingFeedback().to_dict()}

            since = self._determine_since_time()
            feedback_items = self._collect_feedback(platforms, since)
            result = self._build_result(feedback_items, platforms)

            self.last_run_time = datetime.now()
            logger.info(f"ShoppingPlatformFeedbackAgent processed {len(platforms)} platforms, found {len(feedback_items)} items")
            return {"ShoppingFeedback": result.to_dict()}

        except Exception as e:
            logger.error(f"ShoppingPlatformFeedbackAgent failed: {e}", exc_info=True)
            return {"ShoppingFeedback": ShoppingFeedback().to_dict()}

    def _extract_platforms(self, state: Dict[str, Any]) -> List[str]:
        platforms = state.get("platforms", [])
        if isinstance(platforms, str):
            platforms = [platforms]
        elif not isinstance(platforms, list):
            platforms = []
        return platforms

    def _determine_since_time(self) -> datetime:
        if self.last_run_time:
            since = self.last_run_time
        else:
            since = datetime.now() - timedelta(hours=self.lookback_hours)
        max_lookback = datetime.now() - timedelta(hours=self.lookback_hours)
        if since < max_lookback:
            since = max_lookback
        return since

    def _collect_feedback(self, platforms: List[str], since: datetime) -> List[ShoppingFeedbackItem]:
        if self.use_mock:
            return self._generate_mock_feedback(platforms, since)
        return []

    def _generate_mock_feedback(self, platforms: List[str], since: datetime) -> List[ShoppingFeedbackItem]:
        platform_map = {
            "taobao": ShoppingPlatform.TAOBAO,
            "jd": ShoppingPlatform.JD,
            "pinduoduo": ShoppingPlatform.PINDUODUO,
        }
        sentiments = list(Sentiment)

        products = [
            ("SKU1001", "智能手表Pro"),
            ("SKU1002", "无线降噪耳机"),
            ("SKU1003", "便携式充电宝"),
            ("SKU1004", "运动跑鞋"),
            ("SKU1005", "保温杯"),
        ]

        reviews = [
            "质量很好，做工精细，值得购买！",
            "性价比很高，推荐入手。",
            "一般般，没有预期的好。",
            "物流很快，包装很好。",
            "用了一段时间，感觉还不错。",
            "颜色和图片有差异，介意慎拍。",
            "给家人买的，很喜欢。",
            "售后态度很好，问题及时解决了。",
            "已经回购好几次了，品质稳定。",
            "比实体店便宜，正品保障。",
        ]

        items = []
        for platform_name in platforms:
            mapped = platform_map.get(platform_name.lower(), ShoppingPlatform.OTHER)
            for product_id, product_name in random.sample(products, k=min(3, len(products))):
                for i in range(random.randint(1, 3)):
                    published_at = datetime.now() - timedelta(hours=random.randint(0, 23))
                    if published_at < since:
                        continue

                    fb_id = f"shop_{platform_name}_{product_id}_{i}_{int(datetime.now().timestamp())}"
                    if fb_id in self.processed_ids:
                        continue
                    self.processed_ids.add(fb_id)

                    rating = random.choice([5, 5, 4, 4, 4, 3, 3, 2, 1])
                    items.append(ShoppingFeedbackItem(
                        id=fb_id,
                        platform=mapped,
                        product_id=product_id,
                        product_name=product_name,
                        rating=rating,
                        review_content=random.choice(reviews),
                        sentiment=Sentiment.POSITIVE if rating >= 4 else Sentiment.NEUTRAL if rating == 3 else Sentiment.NEGATIVE,
                        is_purchased=True,
                        likes_count=random.randint(0, 200),
                        author_name=f"买家_{random.randint(1000, 9999)}",
                        timestamp=published_at,
                    ))

        return items

    def _build_result(self, items: List[ShoppingFeedbackItem], platforms: List[str]) -> ShoppingFeedback:
        result = ShoppingFeedback(items=items)
        processed = set(item.platform.value for item in items)
        for p in platforms:
            if p in processed:
                result.add_successful_platform(p)
            else:
                result.add_successful_platform(p)
        return result


def create_shopping_platform_feedback_agent(config: Dict[str, Any]):
    agent = ShoppingPlatformFeedbackAgent(config)
    def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        return agent.invoke(state)
    return agent_node


DEFAULT_CONFIG = {
    "lookback_hours": 24,
    "use_mock": True,
}


if __name__ == "__main__":
    agent = ShoppingPlatformFeedbackAgent({"use_mock": True})
    result = agent.invoke({"platforms": ["taobao", "jd", "pinduoduo"]})
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
