"""
CommentAnalyzer — 小红书评论情感分析 + 卖点提取模块。

基于关键词规则对评论进行情感分类（积极/负面/中性），
并从评论中提取具体的产品卖点标签。
"""
import re
from typing import Dict, Any, List
from collections import Counter


# ── 情感关键词 ──

_POSITIVE_KEYWORDS = [
    "好用", "推荐", "回购", "舒服", "好刷", "满意", "效果好", "性价比高",
    "值得", "好闻", "泡沫丰富", "好", "不错", "喜欢", "种草", "安利",
    "爱了", "真香", "绝了", "yyds", "惊艳", "惊喜", "超值", "划算",
    "好看", "颜值高", "质量好", "手感好", "温和", "干净",
    "有效", "改善", "持久", "耐用", "方便", "清新", "白了",
    "亮了", "柔软", "细腻", "专业", "高级", "不刺激", "不伤",
]

_NEGATIVE_KEYWORDS = [
    "不好用", "踩雷", "难用", "失望", "过敏", "刺激", "味道难闻",
    "太贵", "掉毛", "不值", "差", "差评", "垃圾", "退货", "退款",
    "假货", "劣质", "质量差", "不推荐", "浪费", "坑", "后悔",
    "上当", "骗人", "鸡肋", "没用", "没效果", "一般般", "普通",
    "贵", "不划算", "噪音大", "漏水", "坏", "断", "裂", "臭",
    "难闻", "牙龈出血", "出血", "疼", "痛", "过敏", "发炎",
]

# ── 卖点标签及关键词 ──

_SELLING_POINTS = {
    "刷毛柔软": {
        "keywords": ["刷毛软", "刷毛柔软", "毛软", "软毛", "刷毛细腻", "柔软", "软乎乎"],
        "sentiment": "positive",
    },
    "清洁力强": {
        "keywords": ["清洁力", "刷得干净", "去渍", "清洁效果", "清洁力强", "刷干净", "洁净"],
        "sentiment": "positive",
    },
    "美白效果": {
        "keywords": ["美白", "变白", "亮白", "去黄", "白了", "亮了", "提亮"],
        "sentiment": "positive",
    },
    "性价比高": {
        "keywords": ["性价比", "划算", "便宜", "实惠", "超值", "不贵", "平价"],
        "sentiment": "positive",
    },
    "味道好": {
        "keywords": ["味道好", "好闻", "味道舒服", "清新", "清香", "香香的", "不刺激"],
        "sentiment": "positive",
    },
    "护龈": {
        "keywords": ["护龈", "不伤牙龈", "温和", "敏感", "牙龈舒服", "不刺激", "牙龈好"],
        "sentiment": "positive",
    },
    "持久续航": {
        "keywords": ["持久", "续航长", "电量耐用", "充一次", "用很久", "续航", "电池"],
        "sentiment": "positive",
    },
    "颜值高": {
        "keywords": ["好看", "颜值", "包装好看", "颜值高", "精致", "高级感", "设计好看"],
        "sentiment": "positive",
    },
    "噪音小": {
        "keywords": ["噪音小", "安静", "不吵", "静音", "声音小", "无声"],
        "sentiment": "positive",
    },
    "防水好": {
        "keywords": ["防水", "不漏水", "水密", "防溅"],
        "sentiment": "positive",
    },
    # 负面卖点
    "牙龈出血": {
        "keywords": ["牙龈出血", "出血", "流血", "牙龈疼", "牙龈痛"],
        "sentiment": "negative",
    },
    "味道不好": {
        "keywords": ["味道不好", "难闻", "味道奇怪", "味道怪", "臭味"],
        "sentiment": "negative",
    },
    "噪音大": {
        "keywords": ["噪音大", "吵", "声音大", "很吵", "震得慌"],
        "sentiment": "negative",
    },
    "质量差": {
        "keywords": ["质量差", "掉毛", "断了", "裂了", "坏了", "劣质", "做工差"],
        "sentiment": "negative",
    },
}


def _is_negated(text: str, keyword: str) -> bool:
    """检查关键词在文本中是否被否定词（不/没/别）修饰。"""
    idx = text.find(keyword)
    while idx != -1:
        if idx > 0 and text[idx - 1] in ("不", "没", "别"):
            return True
        idx = text.find(keyword, idx + 1)
    return False


def _classify_sentiment(text: str) -> str:
    """对单条评论进行情感分类。负面关键词优先，但被否定的负面词除外（如"不刺激"≠负面）。"""
    # 负面词：命中且未被否定 → 负面
    for kw in _NEGATIVE_KEYWORDS:
        if kw in text and not _is_negated(text, kw):
            return "negative"

    # 正面词：命中 → 正面
    for kw in _POSITIVE_KEYWORDS:
        if kw in text:
            return "positive"

    return "neutral"


def _extract_selling_points(text: str, sentiment: str) -> List[str]:
    """从评论中提取卖点标签。"""
    found = []
    for tag, info in _SELLING_POINTS.items():
        # 只提取与评论情感一致的卖点
        if info["sentiment"] != sentiment:
            continue
        for kw in info["keywords"]:
            if kw in text:
                found.append(tag)
                break
    return found


def analyze_comments(comments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """分析评论列表，返回情感分布和卖点标签。

    Args:
        comments: 评论列表，每条评论需包含 content 字段。

    Returns:
        {
            "total_comments": int,
            "sentiment": {"positive": int, "negative": int, "neutral": int},
            "positive_ratio": float,
            "selling_points": [{"tag": str, "count": int, "sentiment": str}],
            "details": [
                {
                    "content": str,
                    "sentiment": str,
                    "selling_points": [str],
                    "nickname": str,
                }
            ],
        }
    """
    if not comments:
        return {
            "total_comments": 0,
            "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
            "positive_ratio": 0.0,
            "selling_points": [],
            "details": [],
        }

    sentiment_counts = Counter()
    selling_point_counts = Counter()
    details = []

    for comment in comments:
        content = comment.get("content", "") or ""
        if not content.strip():
            continue

        # 情感分类
        sentiment = _classify_sentiment(content)
        sentiment_counts[sentiment] += 1

        # 卖点提取
        points = _extract_selling_points(content, sentiment)
        for point in points:
            selling_point_counts[point] += 1

        details.append({
            "content": content,
            "sentiment": sentiment,
            "selling_points": points,
            "nickname": comment.get("user", {}).get("nickname", ""),
        })

    total = len(details)
    pos_count = sentiment_counts.get("positive", 0)

    # 卖点汇总
    selling_points = []
    for tag, count in selling_point_counts.most_common():
        sentiment = _SELLING_POINTS.get(tag, {}).get("sentiment", "positive")
        selling_points.append({
            "tag": tag,
            "count": count,
            "sentiment": sentiment,
        })

    return {
        "total_comments": total,
        "sentiment": {
            "positive": sentiment_counts.get("positive", 0),
            "negative": sentiment_counts.get("negative", 0),
            "neutral": sentiment_counts.get("neutral", 0),
        },
        "positive_ratio": round(pos_count / total, 2) if total > 0 else 0.0,
        "selling_points": selling_points,
        "details": details,
    }
