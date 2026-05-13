"""
XiaohongshuUpdatesAgent — 小红书数据采集子 agent。

基于 Spider_XHS 项目的小红书 API 封装，监听固定博主的最新笔记。
"""
import os
import sys
import re
import json
import logging
import time as _time
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Any, Optional

import requests as _requests

# 将 Spider_XHS 根目录加入 sys.path，使 apis / xhs_utils 可被导入
_XHS_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent / "agents" / "searcher" / "xhs_spider" / "Spider_XHS-3.0.0")
if _XHS_ROOT not in sys.path:
    sys.path.insert(0, _XHS_ROOT)

from src.agents.searcher.keyword_dicts import match_keywords, BRAND_KEYWORDS, PRODUCT_KEYWORDS, INGREDIENT_KEYWORDS

# 让 Node.js (PyExecJS) 能找到 spider 的 node_modules 中的 crypto-js / jsdom
_XHS_NODE_MODULES = str(Path(_XHS_ROOT) / "node_modules")
_current_node_path = os.environ.get("NODE_PATH", "")
if _XHS_NODE_MODULES not in _current_node_path:
    os.environ["NODE_PATH"] = _XHS_NODE_MODULES + (os.pathsep + _current_node_path if _current_node_path else "")

# JS 文件中用相对路径 require 其他 JS 包，必须从 spider 根目录导入
_cwd = os.getcwd()
os.chdir(_XHS_ROOT)
try:
    from apis.xhs_pc_apis import XHS_Apis
    from xhs_utils.data_util import handle_user_info, handle_note_info
finally:
    os.chdir(_cwd)

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

    # 从 raw_data 中尝试获取粉丝数（搜索 API 可能返回）
    fans = 0
    raw = entry.get("raw_data") or {}
    if isinstance(raw, dict):
        interact = raw.get("interact_info", {})
        fans = _parse_int(interact.get("fans", 0))
        # 也尝试从 note_card 获取
        note_card = raw.get("note_card", {})
        if isinstance(note_card, dict):
            user_info = note_card.get("user", {})
            if isinstance(user_info, dict):
                fans = max(fans, _parse_int(user_info.get("fans", 0)))

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


def _parse_target(target: dict):
    """从 target 配置中解析 user_id / xsec_token / xsec_source（复用 monitor_users.py 逻辑）。"""
    user_id = target.get("user_id", "").strip()
    xsec_token = target.get("xsec_token", "").strip()
    xsec_source = target.get("xsec_source", "pc_search").strip() or "pc_search"
    user_url = target.get("user_url", "").strip()
    if user_url:
        parsed = urlparse(user_url)
        if not user_id:
            user_id = parsed.path.split("/")[-1]
        query = parse_qs(parsed.query)
        if not xsec_token and query.get("xsec_token"):
            xsec_token = query["xsec_token"][0]
        if query.get("xsec_source"):
            xsec_source = query["xsec_source"][0]
    return user_id, xsec_token, xsec_source


def _parse_upload_time(upload_time_str: str) -> Optional[datetime]:
    """将 handle_note_info 输出的 'YYYY-MM-DD HH:MM:SS' 字符串解析为 datetime。"""
    if not upload_time_str:
        return None
    try:
        return datetime.strptime(upload_time_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


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


def _parse_relative_time(text: str) -> Optional[datetime]:
    """解析小红书搜索结果中的时间格式。

    支持:
    - 相对时间: '3分钟前', '2小时前', '昨天', '3天前', '1周前', '2个月前'
    - 月日绝对时间: '04-05', '4-5' (自动推断年份)
    """
    if not text:
        return None
    text = text.strip()
    now = datetime.now()
    try:
        if "分钟" in text:
            mins = int("".join(c for c in text if c.isdigit()) or "0")
            return now - timedelta(minutes=mins)
        if "小时" in text:
            hours = int("".join(c for c in text if c.isdigit()) or "0")
            return now - timedelta(hours=hours)
        if text == "昨天":
            return now - timedelta(days=1)
        if "天" in text:
            days = int("".join(c for c in text if c.isdigit()) or "0")
            return now - timedelta(days=days)
        if "周" in text:
            weeks = int("".join(c for c in text if c.isdigit()) or "0")
            return now - timedelta(weeks=weeks)
        if "个月" in text or "月" in text:
            months = int("".join(c for c in text if c.isdigit()) or "0")
            return now - timedelta(days=months * 30)
        if "年" in text:
            years = int("".join(c for c in text if c.isdigit()) or "0")
            return now - timedelta(days=years * 365)

        # MM-DD 月日格式 (如 "04-05", "4-5")
        import re as _re
        m = _re.match(r'^(\d{1,2})-(\d{1,2})$', text)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                year = now.year
                try:
                    result = datetime(year, month, day)
                except ValueError:
                    return None
                # 如果日期在未来，说明是去年的
                if result > now + timedelta(days=1):
                    result = datetime(year - 1, month, day)
                return result
    except (ValueError, TypeError):
        return None
    return None


def _extract_publish_time(item: dict) -> Optional[datetime]:
    """从搜索结果 note_card 的 corner_tag_info 中提取发布时间。"""
    note_card = item.get("note_card", item)
    corner_tags = note_card.get("corner_tag_info", [])
    if isinstance(corner_tags, list):
        for tag in corner_tags:
            if isinstance(tag, dict) and tag.get("type") == "publish_time":
                return _parse_relative_time(tag.get("text", ""))
    return None


def _parse_note_from_user_api(note: dict, note_url: str) -> dict:
    """解析 get_user_note_info() 返回的笔记数据，输出与 handle_note_info() 相同格式的 dict。

    用户笔记 API 返回结构与搜索 API 不同：没有 note_card 包装层。
    """
    note_id = note.get("note_id", "")
    note_type_raw = note.get("type", "")
    note_type = "视频" if note_type_raw == "video" else "图集"

    user = note.get("user", {})
    user_id = user.get("user_id", "")
    nickname = user.get("nickname") or user.get("nick_name", "")

    title = note.get("display_title", "") or ""
    desc = note.get("desc", "") or ""

    interact_info = note.get("interact_info", {})
    liked_count = _parse_int(interact_info.get("liked_count", 0))
    collected_count = _parse_int(interact_info.get("collected_count", 0))
    comment_count = _parse_int(interact_info.get("comment_count", 0))
    share_count = _parse_int(interact_info.get("share_count", 0))

    # 图片列表
    image_list = []
    cover = note.get("cover", {})
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

    # 时间（用户笔记 API 没有直接返回时间戳，用 detected 时间或忽略）
    upload_time = ""

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
        "tags": [],
        "upload_time": upload_time,
        "ip_location": "",
    }


class XiaohongshuUpdatesAgent:
    """小红书数据采集子 agent，与 WeiboUpdatesAgent 并列。"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cookies_str: str = config.get("xhs_cookies", "")
        self.monitor_targets: list = config.get("xhs_monitor_targets", [])
        self.min_fans: int = config.get("xhs_min_fans", 0)
        self.lookback_hours: int = config.get("lookback_hours", 24)

        self.api = XHS_Apis()
        self.last_run_time: Optional[datetime] = None
        self.processed_updates: set = set()

        # 缓存已查询的用户粉丝数，避免重复请求
        self._fans_cache: Dict[str, int] = {}

    def since_time(self) -> datetime:
        """计算数据回溯起始时间（同 WeiboUpdatesAgent 逻辑）。"""
        if self.last_run_time:
            since = self.last_run_time
        else:
            since = datetime.now() - timedelta(hours=self.lookback_hours)
        max_lookback = datetime.now() - timedelta(hours=self.lookback_hours)
        return max(since, max_lookback)

    def fetch(self, sources: List[str], since: datetime) -> List[OfficialUpdate]:
        """获取小红书更新（固定博主监听）。"""
        if not self.cookies_str:
            logger.warning("XHS cookies 未配置，跳过小红书数据采集")
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
            user_id, xsec_token, xsec_source = _parse_target(target)
            if not user_id:
                logger.warning(f"[XHS] 博主 '{name}' 无法解析 user_id，跳过")
                continue

            # 粉丝数筛选
            if self.min_fans > 0:
                fans = self._get_user_fans(user_id)
                if fans is not None and fans < self.min_fans:
                    logger.debug(f"[XHS] 博主 '{name}' 粉丝数 {fans} < {self.min_fans}，跳过")
                    continue

            # 获取最新笔记
            success, msg, res_json = self.api.get_user_note_info(
                user_id=user_id,
                cursor="",
                cookies_str=self.cookies_str,
                xsec_token=xsec_token,
                xsec_source=xsec_source,
            )
            if not success:
                if self._is_cookie_expired(msg):
                    logger.warning(f"[XHS] Cookie 可能已过期，请更新 XHS_COOKIES: {msg}")
                else:
                    logger.warning(f"[XHS] 博主 '{name}' 获取笔记失败: {msg}")
                continue

            notes = res_json.get("data", {}).get("notes", [])
            for note in notes:
                note_id = note.get("note_id") or note.get("id")
                note_token = note.get("xsec_token") or xsec_token
                if not note_id or not note_token:
                    continue

                note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={note_token}&xsec_source={xsec_source}"

                # 优先调用详情 API 获取真实时间戳
                note_info = self._fetch_note_detail(note_url, note, name)
                if note_info is None:
                    continue

                # 30天过滤
                published_at = _parse_upload_time(note_info.get("upload_time", ""))
                if published_at and published_at < max_age:
                    logger.debug(f"[XHS] 笔记 {note_id} 发布于 {published_at:%Y-%m-%d}，超过30天，跳过")
                    continue

                update = self._to_official_update(note_info, f"xhs:{name}")
                updates.append(update)

        return updates

    def _fetch_note_detail(self, note_url: str, fallback_note: dict, blogger_name: str) -> Optional[dict]:
        """从笔记页面 HTML 提取真实时间戳，失败时回退到列表数据。"""
        # 先用列表数据构建基础 note_info
        try:
            note_info = _parse_note_from_user_api(fallback_note, note_url)
        except Exception:
            return None

        # 尝试从 explore 页面获取真实时间戳
        upload_time = self._fetch_time_from_page(note_url)
        if upload_time:
            note_info["upload_time"] = upload_time
        else:
            logger.debug(f"[XHS] 无法获取笔记时间戳 {note_url[:60]}，使用当前时间")

        return note_info

    def _fetch_time_from_page(self, note_url: str) -> str:
        """从小红书 explore 页面 HTML 中提取笔记发布时间。"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
            # 将 cookie 字符串转为 dict
            cookie_dict = {}
            for pair in self.cookies_str.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    cookie_dict[k.strip()] = v.strip()

            resp = _requests.get(note_url, headers=headers, cookies=cookie_dict, timeout=10)
            if resp.status_code != 200:
                return ""

            # 从 __INITIAL_STATE__ 中提取 time 字段（毫秒级时间戳）
            match = re.search(r'"time"\s*:\s*(\d{13})', resp.text)
            if match:
                ts_ms = int(match.group(1))
                dt = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts_ms / 1000))
                logger.debug(f"[XHS] 从页面提取时间: {dt}")
                return dt

            # 备选：从 window.__INITIAL_STATE__ JSON 中找 noteCard.time
            state_match = re.search(
                r'__INITIAL_STATE__\s*=\s*(\{.*?\})\s*</script>', resp.text, re.DOTALL
            )
            if state_match:
                # 在 INITIAL_STATE 中搜索所有 13 位时间戳，取最小的（即笔记时间）
                ts_all = re.findall(r'(?<!\d)(\d{13})(?!\d)', state_match.group(1))
                if ts_all:
                    # 过滤掉明显是当前时间的（±5 分钟内）
                    now_ms = int(_time.time() * 1000)
                    candidates = [int(t) for t in ts_all if abs(int(t) - now_ms) > 300_000]
                    if candidates:
                        oldest = min(candidates)
                        dt = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(oldest / 1000))
                        logger.debug(f"[XHS] 从 INITIAL_STATE 提取时间: {dt}")
                        return dt

        except Exception as e:
            logger.debug(f"[XHS] 页面时间提取失败: {e}")

        return ""

    def _get_user_fans(self, user_id: str) -> Optional[int]:
        """获取用户粉丝数（带缓存）。"""
        if user_id in self._fans_cache:
            return self._fans_cache[user_id]

        success, msg, res_json = self.api.get_user_info(user_id, self.cookies_str)
        if not success:
            logger.debug(f"[XHS] 获取用户 {user_id} 信息失败: {msg}")
            return None

        try:
            user_data = res_json.get("data", {})
            user_info = handle_user_info(user_data, user_id)
            fans = user_info.get("fans", 0)
            if isinstance(fans, str):
                fans = int(fans)
            self._fans_cache[user_id] = fans
            return fans
        except Exception as e:
            logger.debug(f"[XHS] 解析用户 {user_id} 信息失败: {e}")
            return None

    def _to_official_update(self, note_info: Dict[str, Any], source_url: str) -> OfficialUpdate:
        """将 handle_note_info 输出的 dict 转换为 OfficialUpdate。"""
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
        published_at = _parse_upload_time(upload_time_str) or datetime.now()

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
            update_type=UpdateType.BRAND_CONTENT,  # 由 ContentClassificationAgent 后续分类
            title=title or None,
            content=desc,
            url=note_url or None,
            media_urls=media_urls,
            thumbnail_url=thumbnail_url,
            published_at=published_at,
            engagement_metrics=engagement_metrics,
            raw_data=note_info,
        )

    def _dedup(self, updates: List[OfficialUpdate]) -> List[OfficialUpdate]:
        """去重（同 WeiboUpdatesAgent 逻辑）。"""
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

        多排序策略 + 翻页 + 软时间过滤：
        - 综合排序: note_time=0 不限时间, 取2页 (覆盖高互动老帖子)
        - 最新排序: note_time=3 半年内, 取1页 (保证新鲜度)
        - 点赞排序: note_time=0 不限时间, 取3页 (覆盖高互动帖子)
        - 30天内的帖子无条件保留, 30天外只保留加权互动分≥100的高价值帖子

        Returns:
            List of OfficialUpdate with value_score already applied.
        """
        if not self.cookies_str:
            logger.warning("XHS cookies 未配置，跳过关键词搜索")
            return []

        all_updates: List[OfficialUpdate] = []
        max_age_soft = datetime.now() - timedelta(days=30)   # 软过滤: 30天内无条件保留
        max_age_hard = datetime.now() - timedelta(days=365)  # 硬过滤: 超过1年的不看

        for keyword in keywords:
            logger.info(f"[XHS] 搜索关键词: {keyword}")
            try:
                # ── 多排序策略 + 翻页 ──
                # (sort_type, note_time, pages)
                sort_configs = [
                    (0, 0, 2),   # 综合: 不限时间, 2页 (40条)
                    (1, 3, 1),   # 最新: 半年内,  1页 (20条)
                    (2, 0, 3),   # 点赞: 不限时间, 3页 (60条)
                ]
                sort_names = {0: "综合", 1: "最新", 2: "点赞"}

                all_items = {}  # note_id -> item (去重)
                for sort_type, note_time, pages in sort_configs:
                    sname = sort_names.get(sort_type, str(sort_type))
                    for page in range(1, pages + 1):
                        success, msg, res_json = self.api.search_note(
                            query=keyword,
                            cookies_str=self.cookies_str,
                            page=page,
                            sort_type_choice=sort_type,
                            note_type=0,
                            note_time=note_time,
                        )
                        if not success:
                            logger.debug(f"[XHS] '{keyword}' {sname}排序p{page}搜索失败: {msg}")
                            break  # 某页失败则停止该排序翻页
                        items = res_json.get("data", {}).get("items", [])
                        if not items:
                            break  # 无更多结果
                        for item in items:
                            nid = item.get("id") or item.get("note_id")
                            if nid and nid not in all_items:
                                all_items[nid] = item
                        logger.debug(f"[XHS] '{keyword}' {sname}p{page} 获取 {len(items)} 条")

                if not all_items:
                    logger.info(f"[XHS] 搜索 '{keyword}' 无结果")
                    continue

                logger.info(f"[XHS] 关键词 '{keyword}' 多轮合并共 {len(all_items)} 条去重笔记")

                # 过滤有效笔记
                filtered = []
                for item in all_items.values():
                    model_type = item.get("model_type", "")
                    note_id = item.get("id") or item.get("note_id")
                    xsec_token = item.get("xsec_token")
                    if (model_type in ("note", "note_v2", "note_card") or note_id) and xsec_token:
                        filtered.append(item)

                saved = 0
                for item in filtered:
                    note_id = item.get("id") or item.get("note_id")
                    xsec_source = item.get("xsec_source", "pc_search")
                    note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={item['xsec_token']}&xsec_source={xsec_source}"

                    # 解析笔记信息
                    try:
                        note_data = dict(item)
                        note_data["url"] = note_url
                        note_info = handle_note_info(note_data)
                    except Exception as e:
                        logger.debug(f"[XHS] 解析笔记 {note_id} 失败: {e}")
                        continue

                    # 排除已监听品牌
                    nickname = note_info.get("nickname", "")
                    if _is_monitored_brand(nickname):
                        logger.debug(f"[XHS] 跳过已监听品牌: {nickname}")
                        continue

                    # ── 软时间过滤 ──
                    published_at = _extract_publish_time(item)
                    if not published_at:
                        # 时间缺失 → 跳过（宁可漏不可错）
                        logger.debug(f"[XHS] 笔记 {note_id} 时间缺失，跳过")
                        continue
                    if published_at < max_age_hard:
                        # 超过1年 → 硬性跳过
                        logger.debug(f"[XHS] 笔记 {note_id} 超过1年，跳过")
                        continue

                    # 30天外的帖子 → 需要高互动才保留
                    is_recent = published_at >= max_age_soft
                    if not is_recent:
                        liked = _parse_int(note_info.get("liked_count", 0))
                        collected = _parse_int(note_info.get("collected_count", 0))
                        comment = _parse_int(note_info.get("comment_count", 0))
                        weighted = liked * 1 + comment * 3 + collected * 2
                        if weighted < 100:
                            logger.debug(f"[XHS] 笔记 {note_id} 超过30天且互动低(weighted={weighted})，跳过")
                            continue
                        logger.debug(f"[XHS] 笔记 {note_id} 超过30天但互动高(weighted={weighted})，保留")

                    # 将解析出的真实时间注入 note_info（覆盖 handle_note_info 的空值）
                    note_info["upload_time"] = published_at.strftime("%Y-%m-%d %H:%M:%S")

                    # 去重
                    dedup_key = note_id  # 同一帖子只存一次，不论命中哪个关键词
                    if dedup_key in self.processed_updates:
                        continue

                    update = self._to_official_update(note_info, f"xhs:keyword:{keyword}")
                    self.processed_updates.add(dedup_key)
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
                # 关键词本身是口腔护理相关 → 加相关性分
                oral_kw = ["牙膏", "牙刷", "电动牙刷", "口腔", "牙齿", "美白", "冲牙器", "漱口水", "牙贴"]
                if any(okw in kw for okw in oral_kw):
                    brk = scores.get("scoring_breakdown", {})
                    old_rel = brk.get("relevance_score", 0)
                    if old_rel < 10:
                        boost = 10 - old_rel
                        scores["scoring_breakdown"]["relevance_score"] = 10
                        scores["value_score"] = scores.get("value_score", 0) + boost
                        # 重新分级
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

    @staticmethod
    def _is_cookie_expired(msg: str) -> bool:
        """判断 API 错误是否由 cookie 过期引起。"""
        if not msg:
            return False
        msg_lower = str(msg).lower()
        return any(kw in msg_lower for kw in ["登录", "login", "unauthorized", "auth", "cookie", "sesi"])
