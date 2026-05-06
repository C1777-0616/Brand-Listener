"""
XiaohongshuUpdatesAgent — 小红书数据采集子 agent。

基于 Spider_XHS 项目的小红书 API 封装，监听固定博主的最新笔记。
"""
import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Any, Optional

# 将 Spider_XHS 根目录加入 sys.path，使 apis / xhs_utils 可被导入
_XHS_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent / "agents" / "searcher" / "xhs_spider" / "Spider_XHS-3.0.0")
if _XHS_ROOT not in sys.path:
    sys.path.insert(0, _XHS_ROOT)

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
        """调用详情 API 获取完整笔记信息（含时间戳），失败时回退到列表数据。"""
        try:
            detail_success, detail_msg, detail_json = self.api.get_note_info(
                note_url, self.cookies_str
            )
            if detail_success and detail_json:
                raw = detail_json.get("data", {}).get("items", [{}])[0]
                raw["url"] = note_url
                return handle_note_info(raw)
        except Exception as e:
            logger.debug(f"[XHS] 详情 API 失败 {note_url}: {e}")

        # 回退：用列表数据（无时间戳）
        try:
            return _parse_note_from_user_api(fallback_note, note_url)
        except Exception:
            return None

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

    @staticmethod
    def _is_cookie_expired(msg: str) -> bool:
        """判断 API 错误是否由 cookie 过期引起。"""
        if not msg:
            return False
        msg_lower = str(msg).lower()
        return any(kw in msg_lower for kw in ["登录", "login", "unauthorized", "auth", "cookie", "sesi"])
