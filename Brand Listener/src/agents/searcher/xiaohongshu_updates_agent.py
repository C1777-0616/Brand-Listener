"""
XiaohongshuUpdatesAgent — 小红书数据采集子 agent。

基于 Proxy API 的小红书数据采集，支持搜索、博主监听、评论分析。
"""
import os
import re
import json
import logging
import time as _time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import requests as _requests

from src.agents.searcher.keyword_dicts import match_keywords, BRAND_KEYWORDS, PRODUCT_KEYWORDS, INGREDIENT_KEYWORDS

# ── 新 Proxy API 模块 ──
from src.agents.searcher.xhs_api.note_search import XHSNoteSearch
from src.agents.searcher.xhs_api.user_notes import XHSUserNotes
from src.agents.searcher.xhs_api.note_detail import XHSNoteDetail
from src.agents.searcher.xhs_api.note_comments import XHSNoteComments

from ...data_models.official_updates import OfficialUpdate, Platform, UpdateType

logger = logging.getLogger(__name__)

# ── 帖子价值评分常量 ──

# 监听品牌昵称集合（关键词搜索时排除这些官方账号）
_MONITORED_BRAND_NAMES = {"usmile", "参半", "倍至", "佳洁士", "高露洁", "BOP", "冷酸灵", "舒客"}

# 口腔护理品牌名列表（用于内容相关性评分）
_ORAL_CARE_BRANDS = ["usmile", "参半", "倍至", "佳洁士", "高露洁", "BOP", "冷酸灵", "舒客"]

# 口腔护理直接相关标签（对应 ContentTaggingAgent 的 ai_tags）
_ORAL_TAGS = {"口腔护理", "冲牙器", "电动牙刷", "美白概念", "成分功效"}

# 内容类型判断关键词
_COMPARE_KEYWORDS = ["对比", "测评", "VS", "vs", "Vs", "哪个好", "区别", "横评", "比较"]
_REVIEW_KEYWORDS = ["测评", "体验", "使用", "效果", "亲测", "一个月", "长期", "试用", "上手"]
_KOL_KEYWORDS = ["种草", "好用", "推荐", "安利", "回购", "好物", "必入", "值得"]
_TUTORIAL_KEYWORDS = ["教程", "科普", "怎么选", "怎么用", "方法", "步骤", "攻略", "指南", "技巧"]
_SHARE_KEYWORDS = ["分享", "日常", "开箱", "入手", "买了", "囤货"]

# 2026-01-01 时间戳（用于过滤非2026帖子）
_CUTOFF_2026 = datetime(2026, 1, 1)


def _is_monitored_brand(nickname: str) -> bool:
    """判断昵称是否属于已监听的品牌官方账号（模糊匹配）。"""
    nick_lower = (nickname or "").lower()
    for brand in _MONITORED_BRAND_NAMES:
        if brand.lower() in nick_lower:
            return True
    return False


def _count_brands_in_text(text: str) -> int:
    """统计文本中出现的口腔护理品牌数量。"""
    count = 0
    for brand in _ORAL_CARE_BRANDS:
        if brand.lower() in text.lower():
            count += 1
    return count


def _classify_content_type(text: str, fans: int = 0) -> tuple:
    """判断内容类型，返回 (content_type, content_score)。"""
    brand_count = _count_brands_in_text(text)

    # 多品牌横评对比（最高价值）
    if brand_count >= 2 and any(kw in text for kw in _COMPARE_KEYWORDS):
        return "multi_brand_comparison", 40

    # 单品牌深度测评
    if brand_count >= 1 and any(kw in text for kw in _REVIEW_KEYWORDS):
        return "single_brand_review", 35

    # KOL 推荐种草（粉丝数 >= 1万）
    if fans >= 10000 and any(kw in text for kw in _KOL_KEYWORDS):
        return "kol_recommendation", 30

    # 教程科普
    if any(kw in text for kw in _TUTORIAL_KEYWORDS):
        return "tutorial", 25

    # 一般测评（无品牌但有测评关键词）
    if any(kw in text for kw in _COMPARE_KEYWORDS):
        return "general_review", 25

    # 普通用户分享
    if any(kw in text for kw in _SHARE_KEYWORDS):
        return "user_share", 15

    return "general", 5


def _calc_engagement_score(metrics: dict) -> int:
    """计算互动数据分（0-35）。"""
    liked = _parse_int(metrics.get("liked_count", 0))
    comment = _parse_int(metrics.get("comment_count", 0))
    collected = _parse_int(metrics.get("collected_count", 0))
    share = _parse_int(metrics.get("share_count", 0))

    # 加权互动总分
    total = liked * 1 + comment * 3 + collected * 2 + share * 2

    if total >= 500:
        return 35
    elif total >= 200:
        return 28
    elif total >= 100:
        return 21
    elif total >= 50:
        return 14
    elif total >= 10:
        return 7
    return 0


def _calc_relevance_score(ai_tags: list, text: str = "") -> int:
    """计算内容相关性分（0-25）。

    优先用 ai_tags 评分；ai_tags 为空时回退到文本关键词匹配。
    """
    score = 0
    tag_set = set(ai_tags or [])

    # 含口腔护理直接标签
    if tag_set & _ORAL_TAGS:
        score += 15

    # 含品牌名标签
    brand_related = {"产品种草", "品牌资讯", "口碑背书"}
    if tag_set & brand_related:
        score += 5

    # 含联动/合作标签
    collab_tags = {"品牌联动", "联名合作", "明星代言", "明星互动"}
    if tag_set & collab_tags:
        score += 5

    # ai_tags 为空时，回退到文本关键词匹配
    if score == 0 and text:
        text_lower = text.lower()
        # 口腔护理关键词
        oral_kw = ["牙膏", "牙刷", "电动牙刷", "口腔", "牙齿", "美白", "冲牙器", "漱口水", "牙贴", "洁牙"]
        if any(kw in text for kw in oral_kw):
            score += 15
        # 品牌名
        brand_kw = ["usmile", "笑容加", "参半", "倍至", "佳洁士", "高露洁", "bop", "冷酸灵", "舒客",
                     "云南白药", "黑人", "狮王", "欧乐b", "oral-b", "飞利浦", "philips"]
        if any(kw in text_lower for kw in brand_kw):
            score += 5
        # 产品名
        product_kw = ["电动牙刷", "冲牙器", "水牙线", "漱口水", "牙线", "牙贴", "小光环"]
        if any(kw in text for kw in product_kw):
            score += 5

    return score


def _score_entry(entry: dict) -> dict:
    """对单条帖子进行价值评分，返回评分结果 dict。

    entry 需已包含 engagement_metrics（含 liked_count 等互动数据和 ai_tags）。
    """
    em = entry.get("engagement_metrics") or {}
    title = (entry.get("title") or "").strip()
    content = (entry.get("content") or "").strip()
    text = title + " " + content

    # 从 raw_data 中尝试获取粉丝数
    fans = 0
    raw = entry.get("raw_data") or {}
    if isinstance(raw, dict):
        user = raw.get("user", {})
        if isinstance(user, dict):
            fans = _parse_int(user.get("fans", 0))

    content_type, content_score = _classify_content_type(text, fans)
    engagement_score = _calc_engagement_score(em)
    ai_tags = em.get("ai_tags", [])
    relevance_score = _calc_relevance_score(ai_tags, text)

    total_score = content_score + engagement_score + relevance_score

    # 价值分级
    if total_score >= 70:
        tier = "S"
    elif total_score >= 50:
        tier = "A"
    elif total_score >= 30:
        tier = "B"
    else:
        tier = "C"

    return {
        "value_score": total_score,
        "value_tier": tier,
        "content_type": content_type,
        "scoring_breakdown": {
            "content_score": content_score,
            "engagement_score": engagement_score,
            "relevance_score": relevance_score,
        },
    }


# ── 帖子信息提取（品牌/产品/成分）──

def _extract_post_info(title: str, content: str, nickname: str = "") -> dict:
    """从帖子文本中提取品牌、产品、成分关键词。"""
    text = (title or "") + " " + (content or "") + " " + (nickname or "")
    return match_keywords(text)


def _parse_int(v, default=0) -> int:
    """安全地将值转为 int（处理字符串 '77' 等情况）。"""
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            return default
    return default


def _parse_note_from_api(note: dict, source: str) -> dict:
    """统一解析 Proxy API 返回的笔记数据。

    适用于搜索 API 和用户笔记 API 两种数据源。
    搜索 API 返回 items[].note，用户笔记返回 notes[]（无 note 包装）。
    """
    # 搜索 API 的 items 有 note 包装层：{"model_type": "note", "note": {...}}
    if "note" in note and isinstance(note.get("note"), dict):
        note = note["note"]

    note_id = note.get("note_id") or note.get("id", "")
    note_type_raw = note.get("type", "")
    note_type = "视频" if note_type_raw == "video" else "图集"

    user = note.get("user", {})
    user_id = user.get("userid") or user.get("user_id", "")
    nickname = user.get("nickname") or user.get("nick_name", "")

    title = note.get("display_title") or note.get("title", "") or ""
    desc = note.get("desc", "") or ""

    # 互动数据（两种 API 返回结构不同，做兼容）
    interact_info = note.get("interact_info")
    if interact_info:
        liked_count = _parse_int(interact_info.get("liked_count", 0))
        collected_count = _parse_int(interact_info.get("collected_count", 0))
        comment_count = _parse_int(interact_info.get("comment_count", 0))
        share_count = _parse_int(interact_info.get("share_count", 0))
    else:
        liked_count = _parse_int(note.get("liked_count", 0))
        collected_count = _parse_int(note.get("collected_count", 0))
        comment_count = _parse_int(note.get("comments_count", 0))
        share_count = _parse_int(note.get("share_count", 0))

    # 图片列表
    image_list = []
    images = note.get("images_list", [])
    for img in images:
        if isinstance(img, dict):
            url = img.get("url", "")
        elif isinstance(img, str):
            url = img
        else:
            url = ""
        if url:
            image_list.append(url)

    # 如果没有 images_list，尝试从 cover 获取
    if not image_list:
        cover = note.get("cover", {})
        if isinstance(cover, dict):
            info_list = cover.get("info_list", [])
            for img in info_list:
                url = img.get("url", "")
                if url:
                    image_list.append(url)

    # 视频
    video_addr = None
    video_cover = None
    if note_type == "视频":
        video_cover = image_list[0] if image_list else None
        video_info = note.get("video", {})
        consumer = video_info.get("consumer", {})
        origin_key = consumer.get("origin_video_key")
        if origin_key:
            video_addr = f"https://sns-video-bd.xhscdn.com/{origin_key}"

    # 时间戳：搜索 API 用 timestamp，用户笔记 API 用 create_time
    timestamp = note.get("timestamp") or note.get("create_time")
    upload_time = ""
    if timestamp:
        if isinstance(timestamp, (int, float)):
            if timestamp > 1e12:  # 毫秒级
                timestamp = timestamp / 1000
            try:
                dt = datetime.fromtimestamp(timestamp)
                upload_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError):
                pass

    # xsec_token（搜索 API 返回的笔记需要拼接链接）
    xsec_token = note.get("xsec_token", "")

    # 构建笔记链接
    if xsec_token:
        xsec_source = note.get("xsec_source", "pc_search")
        note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source={xsec_source}"
    else:
        note_url = f"https://www.xiaohongshu.com/explore/{note_id}"

    return {
        "note_id": note_id,
        "note_url": note_url,
        "note_type": note_type,
        "user_id": user_id,
        "home_url": f"https://www.xiaohongshu.com/user/profile/{user_id}",
        "nickname": nickname,
        "avatar": user.get("avatar", ""),
        "title": title,
        "desc": desc,
        "liked_count": liked_count,
        "collected_count": collected_count,
        "comment_count": comment_count,
        "share_count": share_count,
        "video_cover": video_cover,
        "video_addr": video_addr,
        "image_list": image_list,
        "tags": note.get("tag_list", []),
        "upload_time": upload_time,
        "ip_location": note.get("ip_location", ""),
        # 保留原始数据供评分使用
        "_raw_note": note,
    }


class XiaohongshuUpdatesAgent:
    """小红书数据采集子 agent，基于 Proxy API。"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_token: str = config.get("xhs_api_token", "")
        self.monitor_targets: list = config.get("xhs_monitor_targets", [])
        self.min_fans: int = config.get("xhs_min_fans", 0)
        self.lookback_hours: int = config.get("lookback_hours", 24)

        # 初始化 Proxy API 客户端
        self.searcher = XHSNoteSearch(self.api_token)
        self.user_crawler = XHSUserNotes(self.api_token)
        self.detail_crawler = XHSNoteDetail(self.api_token)
        self.comments_crawler = XHSNoteComments(self.api_token)

        self.last_run_time: Optional[datetime] = None
        self.processed_updates: set = set()

    def since_time(self) -> datetime:
        """计算数据回溯起始时间。"""
        if self.last_run_time:
            since = self.last_run_time
        else:
            since = datetime.now() - timedelta(hours=self.lookback_hours)
        max_lookback = datetime.now() - timedelta(hours=self.lookback_hours)
        return max(since, max_lookback)

    def fetch(self, sources: List[str], since: datetime) -> List[OfficialUpdate]:
        """获取小红书更新（固定博主监听）。"""
        if not self.api_token:
            logger.warning("XHS API Token 未配置，跳过小红书数据采集")
            return []

        updates: List[OfficialUpdate] = []

        if self.monitor_targets:
            try:
                blogger_updates = self._fetch_monitored_bloggers(since)
                updates.extend(blogger_updates)
                logger.info(f"[XHS] 固定博主监听获取 {len(blogger_updates)} 条更新")
            except Exception as e:
                logger.error(f"[XHS] 固定博主监听失败: {e}")

        return self._dedup(updates)

    def _fetch_monitored_bloggers(self, since: datetime) -> List[OfficialUpdate]:
        """遍历固定博主列表，获取最新笔记。"""
        updates: List[OfficialUpdate] = []
        max_age = datetime.now() - timedelta(days=30)

        for target in self.monitor_targets:
            if not target.get("enabled", True):
                continue

            name = target.get("name", "未知博主")
            user_id = target.get("user_id", "").strip()
            if not user_id:
                logger.warning(f"[XHS] 博主 '{name}' 缺少 user_id，跳过")
                continue

            # 获取用户笔记（第一页）
            result = self.user_crawler.get_user_notes(user_id)
            if not result.get("success"):
                logger.warning(f"[XHS] 博主 '{name}' 获取笔记失败: {result.get('message')}")
                continue

            data = result.get("data", {})
            notes = data.get("notes", [])

            for note in notes:
                note_id = note.get("note_id") or note.get("id")
                if not note_id:
                    continue

                note_info = _parse_note_from_api(note, f"xhs:{name}")

                # 30天过滤
                published_at = None
                if note_info.get("upload_time"):
                    try:
                        published_at = datetime.strptime(note_info["upload_time"], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass

                if published_at and published_at < max_age:
                    logger.debug(f"[XHS] 笔记 {note_id} 发布于 {published_at:%Y-%m-%d}，超过30天，跳过")
                    continue

                # 2026过滤
                if published_at and published_at < _CUTOFF_2026:
                    continue

                update = self._to_official_update(note_info, f"xhs:{name}")
                updates.append(update)

        return updates

    def _to_official_update(self, note_info: Dict[str, Any], source_url: str) -> OfficialUpdate:
        """将解析后的笔记 dict 转换为 OfficialUpdate。"""
        note_id = note_info.get("note_id", "")
        title = note_info.get("title", "") or ""
        desc = note_info.get("desc", "") or ""
        note_url = note_info.get("note_url", "")

        # 媒体 URL
        media_urls: List[str] = []
        image_list = note_info.get("image_list", [])
        if image_list:
            media_urls.extend(image_list)
        video_addr = note_info.get("video_addr")
        if video_addr:
            media_urls.append(video_addr)

        thumbnail_url = note_info.get("video_cover") or (image_list[0] if image_list else None)

        # 发布时间
        upload_time_str = note_info.get("upload_time", "")
        published_at = datetime.now()
        if upload_time_str:
            try:
                published_at = datetime.strptime(upload_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        # 互动数据
        engagement_metrics = {
            "liked_count": note_info.get("liked_count", 0),
            "collected_count": note_info.get("collected_count", 0),
            "comment_count": note_info.get("comment_count", 0),
            "share_count": note_info.get("share_count", 0),
            "nickname": note_info.get("nickname", ""),
            "user_id": note_info.get("user_id", ""),
            "note_type": note_info.get("note_type", ""),
            "ip_location": note_info.get("ip_location", ""),
            "tags": note_info.get("tags", []),
        }

        return OfficialUpdate(
            id=str(note_id),
            source_url=source_url,
            platform=Platform.XIAOHONGSHU,
            update_type=UpdateType.BRAND_CONTENT,
            title=title or None,
            content=desc,
            url=note_url or None,
            media_urls=media_urls,
            thumbnail_url=thumbnail_url,
            published_at=published_at,
            engagement_metrics=engagement_metrics,
            raw_data=note_info.get("_raw_note", note_info),
        )

    def _dedup(self, updates: List[OfficialUpdate]) -> List[OfficialUpdate]:
        """去重。"""
        unique: List[OfficialUpdate] = []
        for u in updates:
            key = f"{u.source_url}:{u.id}"
            if key not in self.processed_updates:
                self.processed_updates.add(key)
                unique.append(u)
        return unique

    def search_by_keywords(
        self,
        keywords: List[str],
        num_per_keyword: int = 30,
    ) -> List[OfficialUpdate]:
        """按关键词搜索小红书笔记，排除已监听品牌，自动去重。

        多排序策略 + 翻页 + 2026年过滤：
        - 综合排序: 半年内, 取2页 (覆盖高互动帖子)
        - 最新排序: 半年内, 取1页 (保证新鲜度)
        - 点赞排序: 半年内, 取3页 (覆盖高互动帖子)

        Returns:
            List of OfficialUpdate with value_score already applied.
        """
        if not self.api_token:
            logger.warning("XHS API Token 未配置，跳过关键词搜索")
            return []

        all_updates: List[OfficialUpdate] = []

        # 排序映射: 旧sort_type → 新sort参数
        sort_map = {
            0: "general",              # 综合
            1: "time_descending",      # 最新
            2: "popularity_descending", # 点赞
        }

        for keyword in keywords:
            logger.info(f"[XHS] 搜索关键词: {keyword}")
            try:
                # ── 多排序策略 + 翻页 ──
                # (旧sort_type, pages)
                sort_configs = [
                    (0, 2),   # 综合: 2页
                    (1, 1),   # 最新: 1页
                    (2, 3),   # 点赞: 3页
                ]
                sort_names = {0: "综合", 1: "最新", 2: "点赞"}

                all_items = {}  # note_id -> item (去重)
                for sort_type, pages in sort_configs:
                    sname = sort_names.get(sort_type, str(sort_type))
                    sort_param = sort_map.get(sort_type, "general")

                    for page in range(1, pages + 1):
                        result = self.searcher.search(
                            keyword=keyword,
                            page=page,
                            sort=sort_param,
                            note_time="半年内",
                        )

                        if not result.get("success"):
                            logger.debug(f"[XHS] '{keyword}' {sname}排序p{page}搜索失败: {result.get('message')}")
                            break

                        data = result.get("data", {})
                        items = data.get("items", [])
                        if not items:
                            break

                        for item in items:
                            nid = item.get("note_id") or item.get("id") or item.get("note", {}).get("id") or item.get("note", {}).get("note_id")
                            if nid and nid not in all_items:
                                all_items[nid] = item

                        logger.debug(f"[XHS] '{keyword}' {sname}p{page} 获取 {len(items)} 条")

                if not all_items:
                    logger.info(f"[XHS] 搜索 '{keyword}' 无结果")
                    continue

                logger.info(f"[XHS] 关键词 '{keyword}' 多轮合并共 {len(all_items)} 条去重笔记")

                saved = 0
                for note_id, item in all_items.items():
                    note_info = _parse_note_from_api(item, f"xhs:keyword:{keyword}")

                    # 排除已监听品牌
                    nickname = note_info.get("nickname", "")
                    if _is_monitored_brand(nickname):
                        logger.debug(f"[XHS] 跳过已监听品牌: {nickname}")
                        continue

                    # ── 2026年过滤 ──
                    published_at = None
                    if note_info.get("upload_time"):
                        try:
                            published_at = datetime.strptime(note_info["upload_time"], "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            pass

                    if not published_at:
                        logger.debug(f"[XHS] 笔记 {note_id} 时间缺失，跳过")
                        continue
                    if published_at < _CUTOFF_2026:
                        logger.debug(f"[XHS] 笔记 {note_id} 发布于 {published_at:%Y-%m-%d}，非2026年，跳过")
                        continue

                    # 去重（跨关键词）
                    if note_id in self.processed_updates:
                        continue

                    update = self._to_official_update(note_info, f"xhs:keyword:{keyword}")
                    self.processed_updates.add(note_id)
                    all_updates.append(update)
                    saved += 1

                logger.info(f"[XHS] 关键词 '{keyword}' 保存 {saved} 条（去重+过滤后）")

            except Exception as e:
                logger.error(f"[XHS] 搜索关键词 '{keyword}' 异常: {e}")

        return all_updates

    def apply_scores(self, updates: List[OfficialUpdate]) -> None:
        """批量评分+关键词提取，将结果写入 engagement_metrics。"""
        for u in updates:
            entry_dict = {
                "title": u.title,
                "content": u.content,
                "engagement_metrics": u.engagement_metrics,
                "raw_data": u.raw_data,
            }
            scores = _score_entry(entry_dict)

            # 关键词搜索来的帖子：source_url 包含搜索关键词 → 额外相关性加分
            source_url = u.source_url or ""
            if source_url.startswith("xhs:keyword:"):
                kw = source_url.replace("xhs:keyword:", "")
                oral_kw = ["牙膏", "牙刷", "电动牙刷", "口腔", "牙齿", "美白", "冲牙器", "漱口水", "牙贴"]
                if any(okw in kw for okw in oral_kw):
                    brk = scores.get("scoring_breakdown", {})
                    old_rel = brk.get("relevance_score", 0)
                    if old_rel < 10:
                        boost = 10 - old_rel
                        scores["scoring_breakdown"]["relevance_score"] = 10
                        scores["value_score"] = scores.get("value_score", 0) + boost
                        total = scores["value_score"]
                        scores["value_tier"] = "S" if total >= 70 else "A" if total >= 50 else "B" if total >= 30 else "C"

            # 提取帖子中的品牌/产品/成分关键词
            em = u.engagement_metrics or {}
            scores["extracted_info"] = _extract_post_info(
                u.title or "", u.content or "", em.get("nickname", "")
            )
            if u.engagement_metrics is None:
                u.engagement_metrics = {}
            u.engagement_metrics.update(scores)
