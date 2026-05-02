"""
ContentClassificationAgent - classifies OfficialUpdate posts by business content type.

Sits between OfficialUpdatesAgent and BrandCultureAgent in the LangGraph pipeline.
Reads OfficialUpdates from state, rewrites update_type on each entry via keyword rules,
and returns the updated OfficialUpdates. No external IO — pure in-memory processing.

Classification priority (high → low):
  new_product > promotion > kol_collab > user_engagement >
  offline_event > corporate_news > product_content > brand_content (fallback)
"""
import logging
from typing import Dict, Any, List

from ...data_models.official_updates import OfficialUpdates, UpdateType


logger = logging.getLogger(__name__)

# Keyword rules ordered by priority (first match wins)
_RULES: List[tuple[UpdateType, List[str]]] = [
    (UpdateType.NEW_PRODUCT,      ["新品", "上市", "首发", "发布", "推出", "全新", "升级", "新款", "新系列", "问世", "新上"]),
    (UpdateType.PROMOTION,        ["折扣", "优惠", "满减", "秒杀", "限时", "买赠", "大促", "领券", "活动价", "立减", "特价", "限量", "抢购", "包邮"]),
    (UpdateType.KOL_COLLAB,       ["代言", "品牌大使", "官宣", "联名", "挚友", "合作伙伴", "形象大使"]),
    (UpdateType.USER_ENGAGEMENT,  ["抽奖", "转发", "评论抽", "赢取", "话题", "挑战赛", "征集", "投票", "参与", "互动", "晒图", "打卡"]),
    (UpdateType.OFFLINE_EVENT,    ["快闪", "展览", "展位", "线下", "发布会", "现场", "到场", "体验店", "快闪店", "见面会"]),
    (UpdateType.CORPORATE_NEWS,   ["荣获", "入选", "认证", "公益", "社会责任", "声明", "公告", "官方回应", "获奖", "里程碑"]),
    (UpdateType.PRODUCT_CONTENT,  ["使用", "体验", "效果", "测评", "教程", "步骤", "方法", "前后对比", "成分", "配方", "功效", "护理"]),
]


class ContentClassificationAgent:
    """Classifies post content type by keyword matching. No external IO."""

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        ofu_data = state.get("OfficialUpdates")
        if not ofu_data or not ofu_data.get("updates"):
            return {}

        try:
            ofu = OfficialUpdates.from_dict(ofu_data)
        except Exception as e:
            logger.error(f"ContentClassificationAgent: failed to parse OfficialUpdates: {e}")
            return {}

        classified = 0
        for update in ofu.updates:
            text = (update.title or "") + " " + update.content
            update.update_type = self._classify(text)
            classified += 1

        logger.info(f"ContentClassificationAgent: classified {classified} updates")
        return {"OfficialUpdates": ofu.to_dict()}

    def _classify(self, text: str) -> UpdateType:
        for update_type, keywords in _RULES:
            if any(kw in text for kw in keywords):
                return update_type
        return UpdateType.BRAND_CONTENT


def create_content_classification_agent(config: Dict[str, Any]):
    """Factory: returns a LangGraph-compatible node function."""
    agent = ContentClassificationAgent()

    def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        return agent.invoke(state)

    return agent_node
