"""
ContentTaggingAgent - extracts 2-5 content tags + brand collaboration tags per post.

Tags cover: 宣发手法、文案关键词、热点元素、品牌联动.
Stored in update.engagement_metrics['ai_tags'] as list of strings.
Brand collaborations also stored in update.engagement_metrics['collab_partners'].
Idempotent: already-tagged entries are skipped.
No external API — pure keyword matching against title + content + hashtags.
"""
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════
#  品牌联动：外部合作方识别（非口腔品牌）
# ═══════════════════════════════════════════════════

_COLLAB_RULES: List[Tuple[str, List[str], List[str]]] = [
    # (联动类型, 实体关键词, 触发关键词)
    # 实体关键词：本身就是实体名（匹配时作为 collab_entity_names 提取）
    # 触发关键词：泛化信号词（匹配时只归类，不提取实体）

    # 渠道合作（零售/电商）
    ("渠道合作",
     ["WOW COLOUR", "wow colour", "屈臣氏", "丝芙兰", "天猫超市", "天猫",
      "京东", "拼多多", "抖音电商", "小红书商城"],
     ["入驻", "上架", "渠道"]),

    # 漫展/展会/活动
    ("展会合作",
     ["礼品展", "CP32", "漫展", "美博会", "进博会", "品博会", "消博会"],
     ["参展"]),

    # 动漫/影视/游戏 IP
    ("IP联名",
     ["罗小黑", "十日终焉", "草莓熊", "玲娜贝儿", "迪士尼", "漫威",
      "柯南", "航海王", "火影", "蜡笔小新", "宝可梦",
      "LINE FRIENDS", "布朗熊", "可妮兔"],
     ["联名款", "联名", "限定款", "限定系列"]),

    # 明星/代言人/KOL
    ("明星合作",
     ["肖战", "@肖战", "李宏毅", "@李宏毅", "翟潇闻", "@翟潇闻",
      "李佳琦", "@李佳琦Austin", "@李佳琦",
      "林昕宜", "@林昕宜", "周柯宇", "@周柯宇"],
     ["品牌大使", "代言人", "形象大使", "挚友", "海棠们"]),

    # 媒体/综艺
    ("媒体合作",
     ["央视", "CCTV", "央视新闻", "春晚"],
     ["专访", "看片会", "合伙人", "综艺", "节目", "纪录片"]),

    # 公益/慈善
    ("公益合作",
     ["慈善总会", "民政局", "联合国", "基金会"],
     ["公益", "捐赠", "爱心", "志愿者", "世界读书日"]),

    # 跨界品牌（茶饮/美妆/快消等）
    ("跨界品牌",
     ["星巴克", "瑞幸", "奈雪", "喜茶", "茶颜悦色",
      "完美日记", "花西子", "薇诺娜", "盒马", "山姆", "Costco",
      "旺旺", "乐沙儿", "益禾堂", "Hello"],
     []),
]


# ═══════════════════════════════════════════════════
#  品牌别名/吉祥物 → 品牌归属映射
# ═══════════════════════════════════════════════════

_BRAND_ALIASES = {
    "灵灵马": "冷酸灵", "冷少": "冷酸灵",
    "小舒": "舒客",
    "小波": "BOP", "牙小管": "BOP",
    "大佳": "佳洁士",
}


def _normalize_author(author: str) -> str:
    """将品牌昵称/吉祥物替换为正式品牌名。"""
    for alias, brand in _BRAND_ALIASES.items():
        if alias in author:
            author = author.replace(alias, brand)
    return author


# 从 author/feed_title 提取品牌后的标签规则（标题太隐晦时用）
_AUTHOR_TAG_RULES: List[Tuple[str, List[str]]] = [
    ("品牌资讯",   ["冷酸灵", "高露洁", "佳洁士"]),
    ("产品种草",   ["舒客", "BOP", "usmile", "参半", "倍至"]),
]


# ═══════════════════════════════════════════════════
#  内容标签：宣发手法 / 文案关键词 / 热点元素
# ═══════════════════════════════════════════════════

_RULES: List[Tuple[str, List[str]]] = [
    # ═══ 宣发手法 ═══
    ("明星代言",   ["代言", "品牌大使", "形象大使", "代言人", "挚友", "@肖战", "李宏毅", "肖战",
                     "翟潇闻"]),
    ("明星互动",   ["转发 @", "期待与@", "助力", "共闯", "剧透", "粉丝福利",
                     "李佳琦", "周柯宇", "海棠们",
                     "吴磊", "莎莎", "孙颖莎", "生日企划", "拜年祝福"]),
    ("新品发布",   ["新品", "上市", "首发", "发布", "推出", "全新升级", "上新",
                     "即将上线", "问世", "重磅官宣", "亮相"]),
    ("预热造势",   ["倒计时", "揭晓", "解锁", "即将", "敬请期待", "coming",
                     "预告", "悬念", "线索", "预热"]),
    ("抽奖送礼",   ["抽奖", "转发抽", "评论抽", "送", "赠送", "锦鲤", "免费领", "福利",
                     "有奖", "敢不敢", "惊喜盒子", "宠粉", "亲签", "签收",
                     "中奖", "好运", "欧皇", "开工好运"]),
    ("限时优惠",   ["限时", "折扣", "优惠", "满减", "秒杀", "特价", "活动价", "领券",
                     "立减", "包邮", "抢购", "白喝"]),
    ("直播带货",   ["直播", "直播间", "主播", "上链接", "下单", "福利价"]),
    ("联名合作",   ["联名", "跨界", "IP合作", "联名款", "罗小黑", "十日终焉",
                     "入驻", "亮相", "×"]),
    ("线下活动",   ["快闪", "展览", "线下", "发布会", "见面会", "门店", "到店",
                     "礼品展", "CP32", "WOW COLOUR", "wow colour"]),
    ("互动话题",   ["话题", "挑战", "征集", "投票", "打卡", "互动",
                     "进来给", "瞧瞧", "颜色瞧瞧", "晒出",
                     "贴贴", "猜对", "猜猜", "分院", "邀请"]),
    ("KOL种草",   ["种草", "好用", "回购", "安利", "测评", "亲测"]),
    ("教程科普",   ["教程", "步骤", "方法", "技巧", "怎么用", "教你", "攻略",
                     "科普", "一图看懂", "怎么选", "选"]),
    ("场景营销",   ["约会", "出游", "旅行", "日常", "职场", "年会", "毕业",
                     "开学", "上班暂停", "放风"]),
    ("品牌故事",   ["故事", "公益", "社会责任", "爱心", "捐赠", "守护", "如约",
                     "看见", "成为", "幕后", "以书润心", "世界读书日",
                     "童年", "心事", "孩子", "蛀牙", "儿童",
                     "智造揭秘", "Lab to Life"]),
    ("网感互动",   ["嘴里冒出", "奇怪的话", "死手快装", "黑煤球", "半半太装",
                     "秒回", "mbti", "过时", "测了三次", "来点颜色",
                     "跳一个", "谷", "整蛊", "愚人节", "九九成", "稀罕物",
                     "相爱相杀", "next level"]),
    ("产品发布",   ["台式机", "全能旗舰", "重新定义", "旗舰", "焕然一新", "全新",
                     "重磅", "上线", "光芒由她", "闪耀"]),
    ("线下见面",   ["郑州", "广州", "上海", "北京", "深圳", "岛主", "翟",
                     "李宏毅", "见面会", "见面", "快到", "片场"]),
    ("品牌调性",   ["以爱", "温暖", "半半", "相半", "半你", "笑声", "笑容",
                     "清新", "微笑", "嘻唰唰", "洗漱台", "搭子", "搭",
                     "灵灵马", "冷少", "小舒", "小波", "牙小管", "大佳"]),
    ("品牌资讯",   ["专访", "创始人", "CEO", "合伙人", "看片会", "蓝光刷",
                     "冠军", "登榜", "上榜", "获评", "大满贯",
                     "央视", "新闻", "bixdo", "倍至要闻", "NEWS", "媒体报道",
                     "质检"]),
    ("开箱种草",   ["开箱", "分享", "好物", "拆箱", "实拍", "展示",
                     "不二之选", "必须拥有", "拒绝不了"]),
    ("粉丝运营",   ["集合", "宇航员", "别放过", "冲", "冲鸭", "速学",
                     "姐妹们", "家人们", "快来看"]),
    ("产品玩梗",   ["膏手", "嘻唰唰", "最强者", "会馆", "小剧场", "剧本",
                     "剧透", "剧场", "明星阵容", "放""过"]),
    ("内容共创",   ["UGC", "用户投稿", "同人", "创作", "分享你的", "征集作品", "二创"]),

    # ═══ 文案关键词 ═══
    ("限量限定",  ["限量", "限定", "限量版", "限定款", "限定系列", "礼盒"]),
    ("独家专利",  ["专利", "独家", "自研", "黑科技", "创新技术", "标准",
                    "科学的", "揭秘"]),
    ("成分功效",  ["成分", "配方", "功效", "植物", "天然", "温和", "无氟",
                    "氨基酸"]),
    ("美白概念",  ["美白", "亮白", "白牙", "净白", "焕白", "洁白"]),
    ("口腔护理",  ["口腔护理", "护齿", "牙龈", "敏感", "防蛀", "口腔健康",
                    "口腔", "牙膏"]),
    ("冲牙器",   ["冲牙器", "水牙线", "洁牙器", "深层洁净", "清洁力"]),
    ("电动牙刷",  ["电动牙刷", "声波牙刷", "电刷", "刷头"]),
    ("小光环",   ["小光环"]),
    ("颜值外观",  ["颜值", "外观", "设计", "配色", "包装", "便携", "萌化"]),
    ("口碑背书",  ["口碑", "好评", "推荐", "榜单", "销量", "畅销", "热门"]),
    ("育儿亲子",  ["孩子", "儿童", "宝宝", "父母", "孩子第一支",
                    "预防蛀牙", "童年"]),

    # ═══ 热点 ═══
    ("女神节",   ["女神节", "三八", "3.8", "妇女节", "女王节", "38节"]),
    ("春节",     ["春节", "新年", "年货", "除夕", "新春", "团圆", "新的一年",
                   "迎财神", "初五", "初八", "初一", "行花街", "财气"]),
    ("情人节",   ["情人节", "520", "纪念日"]),
    ("618",      ["618", "年中大促"]),
    ("双十一",   ["双十一", "双11", "双十二"]),
    ("世界读书日", ["世界读书日", "读书日", "423"]),
    ("动漫IP",   ["罗小黑", "十日终焉", "CP32", "漫展", "展会", "同人"]),
    ("春季节气", ["春季", "春天", "春日", "踏青", "4月", "五月"]),
    ("夏季",     ["夏季", "夏天", "夏日", "清爽"]),
]


def _extract_tags(text: str) -> List[str]:
    """Extract up to 5 content tags."""
    tags = []
    for tag, keywords in _RULES:
        if any(kw in text for kw in keywords):
            tags.append(tag)
            if len(tags) >= 5:
                break
    return tags


def _extract_collab_info(text: str) -> Tuple[List[str], List[str]]:
    """Detect external brand/partner collaborations.

    Returns:
        (categories, entities) — categories 是联动类型列表，entities 是具体实体名称列表
    """
    categories = []
    entities = []
    for category, entity_kws, trigger_kws in _COLLAB_RULES:
        found_entity = False
        for kw in entity_kws:
            if kw in text:
                categories.append(category)
                # 去掉 @ 前缀存实体名
                entities.append(kw.lstrip("@"))
                found_entity = True
        if not found_entity and trigger_kws:
            if any(kw in text for kw in trigger_kws):
                categories.append(category)
    # 去重保持顺序
    seen_c = set()
    uniq_cats = []
    for c in categories:
        if c not in seen_c:
            seen_c.add(c)
            uniq_cats.append(c)
    seen_e = set()
    uniq_ents = []
    for e in entities:
        if e not in seen_e:
            seen_e.add(e)
            uniq_ents.append(e)
    return uniq_cats, uniq_ents


class ContentTaggingAgent:
    """Extracts content tags + brand collaboration info. No external IO."""

    def tag_updates(self, updates: List[Dict[str, Any]]) -> None:
        to_tag = [u for u in updates if not (u.get("engagement_metrics") or {}).get("ai_tags")]
        if not to_tag:
            return
        logger.info(f"ContentTaggingAgent: tagging {len(to_tag)} entries...")
        tagged = 0
        collab_count = 0
        for u in to_tag:
            title = (u.get("title") or "").strip()
            content = (u.get("content") or "").strip()
            text = title + " " + content

            tags = _extract_tags(text)

            # 回退：title+content 无标签时，合并 author/feed_title 再试
            if not tags:
                em = u.get("engagement_metrics") or {}
                author = em.get("feed_title") or em.get("author") or ""
                author = _normalize_author(author.strip())
                if author:
                    tags = _extract_tags(author + " " + text)

            collab_cats, collab_entities = _extract_collab_info(text)

            # Add collab tag if partners found
            if collab_cats:
                if "品牌联动" not in tags:
                    tags.append("品牌联动")

            if tags:
                if u.get("engagement_metrics") is None:
                    u["engagement_metrics"] = {}
                u["engagement_metrics"]["ai_tags"] = tags
                tagged += 1

                if collab_cats:
                    u["engagement_metrics"]["collab_partners"] = collab_cats
                    collab_count += 1

                if collab_entities:
                    u["engagement_metrics"]["collab_entity_names"] = collab_entities

        logger.info(f"ContentTaggingAgent: tagged {tagged}/{len(to_tag)} entries, "
                     f"{collab_count} with collab partners")

    def retag_collab_entities(self, updates: List[Dict[str, Any]]) -> int:
        """对已有 ai_tags 但缺少 collab_entity_names 的条目补打实体名称。"""
        need_retag = [u for u in updates
                      if (u.get("engagement_metrics") or {}).get("ai_tags")
                      and not (u.get("engagement_metrics") or {}).get("collab_entity_names")]
        if not need_retag:
            return 0
        count = 0
        for u in need_retag:
            title = (u.get("title") or "").strip()
            content = (u.get("content") or "").strip()
            text = title + " " + content
            collab_cats, collab_entities = _extract_collab_info(text)
            if collab_entities:
                u["engagement_metrics"]["collab_entity_names"] = collab_entities
                # 如果之前没有 collab_partners，也补上
                if not u["engagement_metrics"].get("collab_partners"):
                    u["engagement_metrics"]["collab_partners"] = collab_cats
                count += 1
        logger.info(f"ContentTaggingAgent: retagged {count}/{len(need_retag)} entries with collab entities")
        return count

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
