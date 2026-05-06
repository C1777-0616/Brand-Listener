"""
CompetitorInsightAgent - generates per-brand competitive analysis from entries_store.

Pure rule-based, no external IO. Called on-demand via /api/insights/competitor.
Reads entries, groups by brand, and produces structured insights.
"""
import logging
from collections import Counter, defaultdict
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Brand name normalization (same as frontend)
_BRAND_NORMALIZE = {
    '佳洁士Crest': '佳洁士',
    '佳洁士crest': '佳洁士',
    '佳洁士Crest口腔护理': '佳洁士',
    '参半口腔': '参半',
    '参半口腔护理': '参半',
    '舒客Saky': '舒客',
    '舒客saky': '舒客',
    'Saky': '舒客',
    'usmile笑容加': 'usmile',
    'USmile笑容加': 'usmile',
    'bixdo倍至': '倍至',
}


def _normalize_brand(name: str) -> str:
    return _BRAND_NORMALIZE.get(name, name)


def _extract_brand(entry: dict) -> str:
    raw = (entry.get('engagement_metrics', {}).get('feed_title')
           or entry.get('engagement_metrics', {}).get('nickname')
           or entry.get('engagement_metrics', {}).get('author')
           or '')
    import re
    name = re.sub(r'[\s]*(的)?[\s]*(微博|bilibili|b站|小红书|抖音|快手|微信)[\s]*(动态|笔记|视频)?', '', raw, flags=re.I).strip()
    return _normalize_brand(name)


def analyze(entries: List[dict], target_brand: Optional[str] = None) -> Dict[str, Any]:
    """Analyze entries and produce competitive insights.

    Args:
        entries: list of entry dicts from entries_store
        target_brand: if set, only analyze this brand and compare with others

    Returns:
        {
            "brands": {brand_name: {...insights...}},
            "comparison": [...],
            "generated_at": "ISO timestamp"
        }
    """
    # Group entries by brand
    brand_entries: Dict[str, List[dict]] = defaultdict(list)
    for e in entries:
        brand = _extract_brand(e)
        if brand:
            brand_entries[brand].append(e)

    if not brand_entries:
        return {"brands": {}, "comparison": [], "generated_at": datetime.now().isoformat()}

    # Analyze each brand
    brand_insights = {}
    for brand, items in brand_entries.items():
        insight = _analyze_brand(brand, items)
        brand_insights[brand] = insight

    # Generate comparison
    comparison = _compare_brands(brand_insights)

    result = {
        "brands": brand_insights,
        "comparison": comparison,
        "generated_at": datetime.now().isoformat(),
    }

    # If target_brand specified, add it to top level
    if target_brand and target_brand in brand_insights:
        result["target"] = brand_insights[target_brand]
        result["target_brand"] = target_brand

    return result


def _analyze_brand(brand: str, items: List[dict]) -> dict:
    """Compute insights for a single brand."""
    total = len(items)

    # Date range
    dates = []
    for e in items:
        d = e.get('published_at', '')
        if d:
            try:
                dates.append(datetime.fromisoformat(d.replace('Z', '+00:00')))
            except (ValueError, TypeError):
                pass

    date_min = min(dates).strftime('%Y-%m-%d') if dates else None
    date_max = max(dates).strftime('%Y-%m-%d') if dates else None

    # Days span
    days_span = (max(dates) - min(dates)).days + 1 if len(dates) >= 2 else 1
    avg_per_day = round(total / max(days_span, 1), 1)

    # Platforms
    platforms = Counter(e.get('platform', 'unknown') for e in items)

    # Content types
    types = Counter(e.get('update_type', 'brand_content') for e in items)

    # Tags
    all_tags = []
    for e in items:
        tags = e.get('engagement_metrics', {}).get('ai_tags', [])
        all_tags.extend([t for t in tags if t != '品牌联动'])
    tag_counts = Counter(all_tags)
    top_tags = tag_counts.most_common(10)

    # Collab partners
    all_partners = []
    collab_count = 0
    for e in items:
        partners = e.get('engagement_metrics', {}).get('collab_partners', [])
        if partners:
            collab_count += 1
            all_partners.extend(partners)
    partner_counts = Counter(all_partners)

    # Collab types
    collab_types = dict(partner_counts.most_common())

    return {
        "brand": brand,
        "total_posts": total,
        "date_range": {"from": date_min, "to": date_max, "days": days_span},
        "avg_posts_per_day": avg_per_day,
        "platforms": dict(platforms),
        "content_types": dict(types),
        "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
        "collab_count": collab_count,
        "collab_types": collab_types,
    }


def _compare_brands(insights: Dict[str, dict]) -> List[dict]:
    """Generate cross-brand comparison highlights."""
    if len(insights) < 2:
        return []

    brands = sorted(insights.keys(), key=lambda b: insights[b]["total_posts"], reverse=True)
    comparisons = []

    # Posting frequency comparison
    freq_sorted = sorted(brands, key=lambda b: insights[b]["avg_posts_per_day"], reverse=True)
    comparisons.append({
        "dimension": "发布频率",
        "leader": freq_sorted[0],
        "leader_value": f"{insights[freq_sorted[0]]['avg_posts_per_day']} 条/天",
        "ranking": [{"brand": b, "value": f"{insights[b]['avg_posts_per_day']} 条/天"} for b in freq_sorted],
    })

    # Collab activity comparison
    collab_sorted = sorted(brands, key=lambda b: insights[b]["collab_count"], reverse=True)
    comparisons.append({
        "dimension": "联动活跃度",
        "leader": collab_sorted[0],
        "leader_value": f"{insights[collab_sorted[0]]['collab_count']} 条联动帖",
        "ranking": [{"brand": b, "value": f"{insights[b]['collab_count']} 条联动帖"} for b in collab_sorted],
    })

    # Platform coverage
    plat_sorted = sorted(brands, key=lambda b: len(insights[b]["platforms"]), reverse=True)
    comparisons.append({
        "dimension": "平台覆盖",
        "leader": plat_sorted[0],
        "leader_value": f"{len(insights[plat_sorted[0]]['platforms'])} 个平台",
        "ranking": [{"brand": b, "value": f"{len(insights[b]['platforms'])} 个平台"} for b in plat_sorted],
    })

    # Tag diversity
    tag_sorted = sorted(brands, key=lambda b: len(insights[b]["top_tags"]), reverse=True)
    comparisons.append({
        "dimension": "内容多样性",
        "leader": tag_sorted[0],
        "leader_value": f"{len(insights[tag_sorted[0]]['top_tags'])} 个热门标签",
        "ranking": [{"brand": b, "value": f"{len(insights[b]['top_tags'])} 个热门标签"} for b in tag_sorted],
    })

    return comparisons
