"""
ContentTaggingAgent - extracts 2-4 specific content tags per post via keyword rules.

Tags cover: 宣发手法、文案关键词、热点元素.
Tags are stored in update.engagement_metrics['ai_tags'] as a list of strings.
Already-tagged entries are skipped (idempotent).
No external API required — pure keyword matching.
"""
import re
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# ── All tag rules in priority order: (tag, keywords) ──
_RULES: List[Tuple[str, List[str]]] = [
    # 宣发手法
    ("明星代言",   ["代言", "品牌大使", "形象大使", "代言人", "挚友"]),
    ("新品发布",   ["新品", "上市", "首发", "发布", "推出", "全新升级", "上新", "即将上线", "问世"]),
    ("抽奖送礼",   ["抽奖", "转发抽", "评论抽", "送", "赠送", "锦鲤", "免费领"]),
    ("限时优惠",   ["限时", "折扣", "优惠", "满减", "秒杀", "特价", "活动价", "领券", "立减", "包邮", "抢购"]),
    ("直播带货",   ["直播", "直播间", "主播", "上链接", "下单", "福利价"]),
    ("联名合作",   ["联名", "跨界", "IP合作", "联名款"]),
    ("线下活动",   ["快闪", "展览", "线下", "发布会", "见面会", "门店", "到店"]),
    ("互动话题",   ["话题", "挑战", "征集", "投票", "打卡", "互动"]),
    ("KOL种草",   ["种草", "好用", "回购", "安利", "测评", "亲测"]),
    ("教程科普",   ["教程", "步骤", "方法", "技巧", "怎么用", "教你", "攻略", "科普"]),
    ("场景营销",   ["约会", "出游", "旅行", "日常", "职场", "年会", "毕业", "开学"]),
    ("品牌故事",   ["故事", "公益", "社会责任", "爱心", "捐赠", "守护", "守护的", "如约", "看见", "成为", "幕后"]),

    # 文案关键词
    ("限量限定",  ["限量", "限定", "限量版", "限定款", "限定系列", "礼盒"]),
    ("明星同款",  ["明星同款", "同款", "明星推荐"]),
    ("独家专利",  ["专利", "独家", "自研", "黑科技", "创新技术"]),
    ("成分功效",  ["成分", "配方", "功效", "植物", "天然", "温和", "无氟", "氨基酸"]),
    ("美白概念",  ["美白", "亮白", "白牙", "净白", "焕白", "洁白"]),
    ("口腔护理",  ["口腔护理", "护齿", "牙龈", "敏感", "防蛀", "口腔健康", "口腔"]),
    ("冲牙器",   ["冲牙器", "水牙线", "洁牙器"]),
    ("电动牙刷",  ["电动牙刷", "声波牙刷", "牙刷"]),
    ("颜值外观",  ["颜值", "外观", "设计", "配色", "包装", "便携", "小光环"]),
    ("口碑背书",  ["口碑", "好评", "推荐", "榜单", "销量", "畅销"]),

    # 热点
    ("女神节",   ["女神节", "三八", "3.8", "妇女节", "女王节", "38节"]),
    ("春节",     ["春节", "新年", "年货", "除夕", "新春", "团圆"]),
    ("情人节",   ["情人节", "520", "纪念日"]),
    ("618",      ["618", "年中大促"]),
    ("双十一",   ["双十一", "双11", "双十二"]),
    ("春季",     ["春季", "春天", "春日", "踏青"]),
    ("夏季",     ["夏季", "夏天", "夏日", "清爽"]),
    ("秋冬",     ["秋冬", "冬日", "温暖"]),
    ("毕业季",   ["毕业", "毕业季"]),
    ("开学季",   ["开学", "开学季"]),
    ("旅行季",   ["旅行", "出游"]),
]


def _extract_tags(text: str) -> List[str]:
    """Extract up to 4 tags from text, one match per rule, in priority order."""
    tags = []
    for tag, keywords in _RULES:
        if any(kw in text for kw in keywords):
            tags.append(tag)
            if len(tags) >= 4:
                break
    return tags


class ContentTaggingAgent:
    """Extracts content-specific tags via local keyword rules. No external IO."""

    def tag_updates(self, updates: List[Dict[str, Any]]) -> None:
        to_tag = [u for u in updates if not (u.get("engagement_metrics") or {}).get("ai_tags")]
        if not to_tag:
            return
        logger.info(f"ContentTaggingAgent: tagging {len(to_tag)} entries...")
        tagged = 0
        for u in to_tag:
            title = (u.get("title") or "").strip()
            content = (u.get("content") or "").strip()
            text = title + " " + content
            tags = _extract_tags(text)
            if tags:
                if u.get("engagement_metrics") is None:
                    u["engagement_metrics"] = {}
                u["engagement_metrics"]["ai_tags"] = tags
                tagged += 1
        logger.info(f"ContentTaggingAgent: tagged {tagged}/{len(to_tag)} entries")

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        ofu_data = state.get("OfficialUpdates")
        if not ofu_data or not ofu_data.get("updates"):
            return {}
        updates = ofu_data["updates"]
        self.tag_updates(updates)
        return {"OfficialUpdates": ofu_data}


def create_content_tagging_agent(config: Dict[str, Any]):
    agent = ContentTaggingAgent()

    def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        return agent.invoke(state)

    return agent_node
