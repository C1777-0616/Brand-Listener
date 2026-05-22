"""
CommentAnalyzer — 小红书评论情感分析 + 卖点提取模块。

使用 BettaFish 多语言情感分析模型（DistilBERT）对评论进行情感分类，
并从评论中提取具体的产品卖点标签。
"""
import os
import sys
import re
from typing import Dict, Any, List
from collections import Counter

# 直接导入 BettaFish sentiment_analyzer 模块（避免触发 InsightEngine.__init__ 加载无关依赖）
_bf_sa_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "BettaFish", "InsightEngine", "tools"))
if _bf_sa_path not in sys.path:
    sys.path.insert(0, _bf_sa_path)

import sentiment_analyzer as _bf_sa
analyze_sentiment = _bf_sa.analyze_sentiment
SentimentResult = _bf_sa.SentimentResult

# 5级 → 3级 映射
_LABEL_MAP = {
    "非常负面": "negative",
    "负面": "negative",
    "中性": "neutral",
    "正面": "positive",
    "非常正面": "positive",
}


def _classify_sentiment(text: str) -> str:
    """调用 BettaFish 模型对单条评论进行情感分类，返回 positive/negative/neutral。"""
    result = analyze_sentiment(text)
    if isinstance(result, SentimentResult) and result.success:
        return _LABEL_MAP.get(result.sentiment_label, "neutral")
    return "neutral"


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


def _extract_selling_points(text: str, sentiment: str) -> List[str]:
    """从评论中提取卖点标签。"""
    found = []
    for tag, info in _SELLING_POINTS.items():
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

    # 批量提取文本
    texts = []
    valid_comments = []
    for comment in comments:
        content = comment.get("content", "") or ""
        if content.strip():
            texts.append(content)
            valid_comments.append(comment)

    if not texts:
        return {
            "total_comments": 0,
            "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
            "positive_ratio": 0.0,
            "selling_points": [],
            "details": [],
        }

    # 批量情感分析
    batch_result = analyze_sentiment(texts)

    sentiment_counts = Counter()
    selling_point_counts = Counter()
    details = []

    for i, comment in enumerate(valid_comments):
        content = texts[i]

        # 从批量结果获取情感
        if hasattr(batch_result, "results") and i < len(batch_result.results):
            r = batch_result.results[i]
            if r.success:
                sentiment = _LABEL_MAP.get(r.sentiment_label, "neutral")
            else:
                sentiment = "neutral"
        else:
            sentiment = "neutral"

        sentiment_counts[sentiment] += 1

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

    selling_points = []
    for tag, count in selling_point_counts.most_common():
        sp_sentiment = _SELLING_POINTS.get(tag, {}).get("sentiment", "positive")
        selling_points.append({
            "tag": tag,
            "count": count,
            "sentiment": sp_sentiment,
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
