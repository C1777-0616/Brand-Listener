"""
数据转换层：将 entries_store 数据转换为 BettaFish ReportEngine 所需的 3 份 Markdown 报告。

输出：
- report_query: 品牌声量统计、平台分布、趋势分析
- report_media: KOL合作、内容类型、热门帖子
- report_insight: 标签分析、关键词、用户反馈洞察
"""

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple


def _filter_by_days(entries: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    """按日期范围过滤条目。"""
    if days <= 0:
        return entries
    cutoff = datetime.now() - timedelta(days=days)
    filtered = []
    for e in entries:
        pub = e.get("published_at")
        if not pub:
            filtered.append(e)
            continue
        try:
            if isinstance(pub, str):
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            else:
                dt = pub
            if dt.replace(tzinfo=None) >= cutoff:
                filtered.append(e)
        except (ValueError, TypeError):
            filtered.append(e)
    return filtered


def _safe_str(text: Any) -> str:
    """安全取字符串，None 返回空串。"""
    if not text:
        return ""
    return str(text).strip()


def generate_query_report(entries: List[Dict[str, Any]], days: int) -> str:
    """生成报告1：品牌声量统计、平台分布、趋势分析。"""
    entries = _filter_by_days(entries, days)
    total = len(entries)

    # 平台分布
    platform_counter = Counter(e.get("platform", "unknown") for e in entries)
    platform_lines = "\n".join(
        f"- {p}: {c} 条 ({c/total*100:.1f}%)" for p, c in platform_counter.most_common()
    )

    # 日均发文
    date_counter = Counter()
    for e in entries:
        pub = e.get("published_at", "")
        if pub:
            try:
                dt = datetime.fromisoformat(str(pub).replace("Z", "+00:00"))
                date_counter[dt.strftime("%Y-%m-%d")] += 1
            except (ValueError, TypeError):
                pass
    daily_avg = sum(date_counter.values()) / max(len(date_counter), 1)

    # 每日趋势（最近 N 天）
    trend_lines = ""
    if date_counter:
        sorted_dates = sorted(date_counter.keys(), reverse=True)[:14]
        sorted_dates.reverse()
        trend_lines = "\n".join(
            f"- {d}: {date_counter[d]} 条" for d in sorted_dates
        )

    # 品牌/博主 Top
    brand_counter = Counter()
    for e in entries:
        em = e.get("engagement_metrics") or {}
        nickname = em.get("nickname") or em.get("author") or ""
        if nickname:
            brand_counter[nickname] += 1
    brand_lines = "\n".join(
        f"- {name}: {cnt} 条" for name, cnt in brand_counter.most_common(10)
    )

    # 来源 URL 统计
    source_counter = Counter(e.get("source_url", "") for e in entries if e.get("source_url"))
    source_lines = "\n".join(
        f"- {url}: {cnt} 条" for url, cnt in source_counter.most_common(5)
    )

    return f"""# 品牌声量统计报告

## 数据概览
- 监测周期：最近 {days} 天
- 总条目数：{total} 条
- 日均发文：{daily_avg:.1f} 条
- 活跃平台：{len(platform_counter)} 个

## 平台分布
{platform_lines}

## 发文趋势（最近14天）
{trend_lines}

## 活跃品牌/博主 Top 10
{brand_lines}

## 主要来源
{source_lines}
"""


def generate_media_report(entries: List[Dict[str, Any]], days: int) -> str:
    """生成报告2：KOL合作、内容类型、热门帖子。"""
    entries = _filter_by_days(entries, days)
    total = len(entries)

    # 内容类型分布
    type_counter = Counter(e.get("update_type", "unknown") for e in entries)
    type_labels = {
        "new_product": "新品发布", "promotion": "促销活动", "kol_collab": "KOL合作",
        "user_engagement": "用户互动", "offline_event": "线下活动", "corporate_news": "企业新闻",
        "product_content": "产品内容", "brand_content": "品牌内容",
    }
    type_lines = "\n".join(
        f"- {type_labels.get(t, t)}: {c} 条 ({c/total*100:.1f}%)"
        for t, c in type_counter.most_common()
    )

    # KOL 合作分析
    kol_entries = [e for e in entries if e.get("update_type") == "kol_collab"]
    kol_partners = Counter()
    for e in kol_entries:
        em = e.get("engagement_metrics") or {}
        for p in (em.get("collab_partners") or []):
            kol_partners[p] += 1
        for p in (em.get("collab_entity_names") or []):
            kol_partners[p] += 1
    kol_lines = "\n".join(
        f"- {name}: {cnt} 次合作" for name, cnt in kol_partners.most_common(10)
    ) if kol_partners else "暂无 KOL 合作数据"

    # 热门帖子（按 engagement 简单排序）
    for e in entries:
        em = e.get("engagement_metrics") or {}
        likes = em.get("likes", 0) or 0
        comments = em.get("comments_count", 0) or 0
        shares = em.get("shares", 0) or 0
        e["_score"] = likes + comments * 2 + shares * 3

    sorted_entries = sorted(entries, key=lambda x: x.get("_score", 0), reverse=True)
    hot_lines = []
    for e in sorted_entries[:10]:
        title = _safe_str(e.get("title"))[:60] or "(无标题)"
        platform = e.get("platform", "unknown")
        score = e.get("_score", 0)
        url = e.get("url", "")
        hot_lines.append(f"- [{platform}] {title} (热度:{score}) {url}")
    hot_text = "\n".join(hot_lines) if hot_lines else "暂无数据"

    return f"""# 内容分析报告

## 监测概况
- 监测条目：{total} 条
- KOL 合作内容：{len(kol_entries)} 条

## 内容类型分布
{type_lines}

## KOL 合作分析
{kol_lines}

## 热门帖子 Top 10
{hot_text}
"""


def generate_insight_report(entries: List[Dict[str, Any]], days: int) -> str:
    """生成报告3：标签分析、关键词、洞察摘要。"""
    entries = _filter_by_days(entries, days)
    total = len(entries)

    # 标签统计
    tag_counter = Counter()
    for e in entries:
        em = e.get("engagement_metrics") or {}
        for t in (em.get("ai_tags") or []):
            tag_counter[t] += 1
    tag_lines = "\n".join(
        f"- {tag}: {cnt} 次 ({cnt/total*100:.1f}%)"
        for tag, cnt in tag_counter.most_common(15)
    ) if tag_counter else "暂无标签数据"

    type_labels = {
        "new_product": "新品发布", "promotion": "促销活动", "kol_collab": "KOL合作",
        "user_engagement": "用户互动", "offline_event": "线下活动", "corporate_news": "企业新闻",
        "product_content": "产品内容", "brand_content": "品牌内容",
    }

    # 平台×类型交叉分析
    cross = defaultdict(Counter)
    for e in entries:
        p = e.get("platform", "unknown")
        t = e.get("update_type", "unknown")
        cross[p][t] += 1
    cross_lines = []
    for platform, types in sorted(cross.items(), key=lambda x: sum(x[1].values()), reverse=True):
        type_summary = ", ".join(
            f"{type_labels.get(t, t)}:{c}" for t, c in types.most_common(3)
        )
        cross_lines.append(f"- {platform}: {type_summary}")
    cross_text = "\n".join(cross_lines) if cross_lines else "暂无数据"

    # OCR 品牌识别
    ocr_brands = Counter()
    for e in entries:
        em = e.get("engagement_metrics") or {}
        ocr = em.get("ocr_analysis") or {}
        for b in (ocr.get("brands") or []):
            ocr_brands[b] += 1
    ocr_lines = "\n".join(
        f"- {brand}: {cnt} 次" for brand, cnt in ocr_brands.most_common(10)
    ) if ocr_brands else "暂无 OCR 品牌识别数据"

    return f"""# 洞察分析报告

## 数据规模
- 总条目：{total} 条
- 覆盖平台：{len(cross)} 个

## 标签分布 Top 15
{tag_lines}

## 平台×类型交叉分析
{cross_text}

## OCR 品牌识别 Top 10
{ocr_lines}
"""


def convert_entries_to_reports(
    entries_store: Dict[str, Any],
    days: int = 30,
) -> Tuple[str, str, str]:
    """
    将 entries_store 转换为 3 份 Markdown 报告文本。

    Args:
        entries_store: entries_store dict (key→entry)
        days: 统计天数

    Returns:
        (query_report, media_report, insight_report) 三份 Markdown 字符串
    """
    entries = list(entries_store.values())
    if not entries:
        empty = "# 暂无数据\n\n当前 entries_store 为空，请先运行数据采集流水线。"
        return empty, empty, empty

    report_query = generate_query_report(entries, days)
    report_media = generate_media_report(entries, days)
    report_insight = generate_insight_report(entries, days)

    return report_query, report_media, report_insight
