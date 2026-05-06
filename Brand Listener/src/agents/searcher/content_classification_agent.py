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
    (UpdateType.NEW_PRODUCT,      ["新品", "上市", "首发", "发布", "推出", "全新", "升级", "新款", "新系列", "问世", "新上", "重磅登场", "全新上线", "焕新"]),
    (UpdateType.PROMOTION,        ["折扣", "优惠", "满减", "秒杀", "限时", "买赠", "大促", "领券", "活动价", "立减", "特价", "限量", "抢购", "包邮",
                                   "福利", "赠品", "薅羊毛", "半价", "买一送", "立享", "狂欢价", "到手价", "专属价"]),
    (UpdateType.KOL_COLLAB,       ["代言", "品牌大使", "官宣", "联名", "挚友", "合作伙伴", "形象大使",
                                   "携手", "同款", "联袂", "冠军", "明星", "推荐官", "体验官", "首席", "合作款", "×"]),
    (UpdateType.USER_ENGAGEMENT,  ["抽奖", "转发", "评论抽", "赢取", "话题", "挑战赛", "征集", "投票", "参与", "互动", "晒图", "打卡",
                                   "揪", "一起", "交换", "分享", "许愿", "安利", "留下", "说说", "猜猜", "聊聊", "选选",
                                   "半半", "助力", "进来", "瞧瞧", "色环", "选择", "搭子", "速学", "教会", "大法"]),
    (UpdateType.OFFLINE_EVENT,    ["快闪", "展览", "展位", "线下", "发布会", "现场", "到场", "体验店", "快闪店", "见面会",
                                   "参展", "礼品展", "亮相", "登场", "开展", "探店", "门店", "专柜", "民勤", "片场"]),
    (UpdateType.CORPORATE_NEWS,   ["荣获", "入选", "认证", "公益", "社会责任", "声明", "公告", "官方回应", "获奖", "里程碑",
                                   "周年", "战略合作", "签约", "融资", "上市企业", "财报", "排名", "榜单", "世界口腔健康日"]),
    (UpdateType.PRODUCT_CONTENT,  ["使用", "体验", "效果", "测评", "教程", "步骤", "方法", "前后对比", "成分", "配方", "功效", "护理",
                                   "科普", "怎么", "如何", "一图看懂", "选购", "指南", "对比", "区别", "原理", "干货",
                                   "走进", "背后", "故事", "坚守", "偏执", "热爱", "耗时", "智造", "制造", "实验室",
                                   "冲牙器", "电动牙刷", "口腔医生", "蛀牙", "好物", "推荐", "必备", "守护", "清洁",
                                   "上新", "即将上线", "台式机", "旗舰", "小光环", "净启", "重新定义"]),
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
