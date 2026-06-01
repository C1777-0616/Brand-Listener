"""
Brand Listener - FastAPI Web Server

Provides a web interface and REST API for the LangGraph pipeline.
Serves frontend static files and exposes endpoints to trigger/manage the pipeline.
"""
import sys
import json
import re
import os
import logging
import time as _time
from pathlib import Path
from typing import Dict, Any, Optional
from collections import Counter, defaultdict
from datetime import datetime, timedelta

# Ensure project root is in path
_root = Path(__file__).parent
sys.path.insert(0, str(_root))

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    _HAS_APSCHEDULER = True
except ImportError:
    _HAS_APSCHEDULER = False
    logging.getLogger("server").warning(
        "apscheduler not installed — auto-refresh disabled. Run: pip install apscheduler"
    )

try:
    from watchfiles import watch as _watch_files
    _HAS_WATCHFILES = True
except ImportError:
    _HAS_WATCHFILES = False

from src.utils.config import get_api_config
from src.brand_config import get_brand_config_manager, BrandConfig
from langgraph.workflow import run_full_pipeline, print_pipeline_result
from src.agents.searcher.content_tagging_agent import ContentTaggingAgent

logger = logging.getLogger("server")

# ── 口腔护理行业过滤 ──
_ORAL_KEYWORDS = [
    "牙膏", "牙刷", "电动牙刷", "口腔", "牙齿", "美白", "冲牙器", "漱口水", "牙线", "牙贴",
    "toothpaste", "toothbrush", "oral", "dental", "teeth", "whitening", "mouthwash",
    "usmile", "笑容加", "参半", "倍至", "佳洁士", "高露洁", "BOP", "冷酸灵", "舒客",
    "云南白药", "黑人牙膏", "狮王", "欧乐B", "Oral-B", "飞利浦sonicare", "Sonicare",
    "洁牙", "口臭", "蛀牙", "龋齿", "正畸", "牙科", "洗牙", "补牙", "拔牙",
]

# 永久黑名单：与口腔护理无关的 FOLO 订阅来源
_BLOCKED_SOURCES = [
    "1x.com", "macrumors.com", "github.blog", "vox.com", "smzdm.com",
    "theverge.com", "tophub.today", "apod.nasa.gov", "nature.com",
    "x.com/elonmusk", "x.com/GeminiApp", "x.com/sama",
    "x.com/AnthropicAI", "x.com/OpenAI",
    "t.me/s/durov",
    "youtube.com/channel/UCXuqSBlHAE6Xw",
    "youtube.com/channel/UCrDwWp7EBBv4",
]

# 口腔医院/诊所广告过滤（仅用于小红书关键词搜索帖子）
_CLINIC_NICKNAME_BLOCKERS = [
    "口腔医院", "口腔门诊", "口腔诊所", "牙科诊所", "口腔中心",
    "口腔专科", "齿科", "齿科美学", "家庭齿科", "牙齿贴面",
    "口腔连锁", "口腔",  # 昵称含"口腔"基本都是诊所账号
]
_CLINIC_CONTENT_BLOCKERS = [
    "口腔医院", "口腔门诊", "牙科诊所", "种植牙", "全瓷牙",
    "根管治疗", "烤瓷牙", "隐形矫正", "牙周治疗", "全瓷贴面",
    "瓷贴面", "树脂贴面", "义诊", "公益口腔",
]

def _is_clinic_ad(entry: dict) -> bool:
    """判断帖子是否为口腔医院/诊所广告。"""
    em = entry.get("engagement_metrics") or {}
    nickname = (entry.get("nickname") or entry.get("author")
                or em.get("nickname") or "").lower()
    for kw in _CLINIC_NICKNAME_BLOCKERS:
        if kw in nickname:
            return True
    text = f"{entry.get('title', '')} {entry.get('content', '')}".lower()
    for kw in _CLINIC_CONTENT_BLOCKERS:
        if kw in text:
            return True
    return False


def _is_oral_related(entry: dict) -> bool:
    """判断条目是否与口腔护理行业相关。先检查来源黑名单，再检查文本关键词，最后检查 OCR 结果。"""
    src = (entry.get("source_url") or "").lower()
    if any(blocked.lower() in src for blocked in _BLOCKED_SOURCES):
        return False
    text = " ".join(filter(None, [
        entry.get("title", ""),
        entry.get("content", ""),
        (entry.get("engagement_metrics") or {}).get("nickname", ""),
        (entry.get("engagement_metrics") or {}).get("feed_title", ""),
        (entry.get("engagement_metrics") or {}).get("author", ""),
    ]))
    text_lower = text.lower()
    if any(kw.lower() in text_lower for kw in _ORAL_KEYWORDS):
        return True
    # OCR 结果也纳入判断
    ocr = (entry.get("engagement_metrics") or {}).get("ocr_analysis") or {}
    return bool(ocr.get("brands") or ocr.get("products"))

# ── FastAPI App ──

app = FastAPI(title="Brand Listener API", version="0.1.0")

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:8001",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8001",
        "http://192.168.103.186:8000",
        "http://192.168.103.186:8001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Concurrency locks ──
import threading
_store_lock = threading.Lock()
_pipeline_lock = threading.Lock()

# ── Background pipeline runner ──

def _retag_missing():
    """对 entries_store 里缺少 ai_tags 或 collab_entity_names 的条目补打标签，并持久化。"""
    updates = list(entries_store.values())
    tagger = ContentTaggingAgent()
    changed = False

    # 补打缺失的 ai_tags
    missing_tags = [u for u in updates if not (u.get("engagement_metrics") or {}).get("ai_tags")]
    if missing_tags:
        logger.info(f"Retagging {len(missing_tags)} entries missing ai_tags...")
        tagger.tag_updates(missing_tags)
        changed = True

    # 补打缺失的 collab_entity_names
    retagged = tagger.retag_collab_entities(updates)
    if retagged:
        changed = True

    if changed:
        try:
            with _store_lock:
                _save_store_atomically()
        except Exception as e:
            logger.warning(f"Could not save entries_store after retag: {e}")


def _ocr_missing():
    """对 entries_store 里缺少 ocr_analysis 的条目补做 OCR，并持久化。

    同时清除之前因 cookie 失败产生的空 ocr_analysis，以便重新处理。
    """
    from src.agents.searcher.ocr_agent import OCRAgent
    from src.utils.config import get_ocr_agent_config

    entries_to_process = []
    for u in entries_store.values():
        em = u.get("engagement_metrics") or {}
        ocr = em.get("ocr_analysis")
        if ocr:
            # 清除之前因 cookie 过期导致下载失败的空结果：
            # ocr_analysis 存在但 brands/products/raw_texts 全空，且有 media 可处理
            has_media = (u.get("media_urls") or u.get("thumbnail_url")
                         or (u.get("raw_data") or {}).get("image_list"))
            is_stale = (not ocr.get("brands") and not ocr.get("products")
                        and not ocr.get("raw_texts") and not ocr.get("error")
                        and has_media)
            if is_stale:
                del em["ocr_analysis"]  # 清除以便重新处理
            else:
                continue  # 有效的 ocr_analysis，跳过
        # 检查是否有媒体可处理
        if (u.get("media_urls") or u.get("thumbnail_url")
                or (u.get("raw_data") or {}).get("image_list")):
            entries_to_process.append(u)

    if not entries_to_process:
        return

    config = get_ocr_agent_config()
    if not config.get("ocr_enabled", True):
        return
    # 批量 OCR 只处理 1 张图/条以加快速度
    config["ocr_max_images"] = 1

    logger.info(f"Running OCR on {len(entries_to_process)} entries missing ocr_analysis...")
    agent = OCRAgent(config)
    processed = 0
    for entry in entries_to_process:
        try:
            agent.process_entry(entry, force=True)
            processed += 1
            if processed % 10 == 0:
                logger.info(f"OCR progress: {processed}/{len(entries_to_process)} entries processed")
                # 中间持久化
                try:
                    with _store_lock:
                        _save_store_atomically()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"OCR failed for {entry.get('id', '?')}: {e}")
    logger.info(f"OCR completed: {processed}/{len(entries_to_process)} entries processed")

    # 持久化
    try:
        with _store_lock:
            _save_store_atomically()
    except Exception as e:
        logger.warning(f"Could not save entries_store after OCR: {e}")


def _purge_clinic_ads():
    """从 entries_store 中删除已有的口腔医院广告（仅 xhs:keyword 条目）。"""
    to_remove = [k for k, v in entries_store.items()
                 if k.startswith("xhs:keyword:") and _is_clinic_ad(v)]
    for k in to_remove:
        del entries_store[k]
    if to_remove:
        logger.info(f"Purged {len(to_remove)} clinic ads from xhs:keyword entries")
        try:
            with _store_lock:
                _save_store_atomically()
        except Exception as e:
            logger.warning(f"Could not save entries_store after purge: {e}")


def _dedup_entries_store():
    """启动时按 note_id 去重：同一 note_id 只保留一条。"""
    from collections import defaultdict
    groups = defaultdict(list)
    for k, v in entries_store.items():
        note_id = k.rsplit(":", 1)[-1]
        groups[note_id].append((k, v))

    to_remove = []
    for note_id, items in groups.items():
        if len(items) <= 1:
            continue
        # 保留 source_url 最短的（品牌名 key 优先），其次保留先入库的
        items.sort(key=lambda x: (len(x[1].get("source_url", "")), x[0]))
        for k, _ in items[1:]:
            to_remove.append(k)

    for k in to_remove:
        del entries_store[k]
    if to_remove:
        logger.info(f"Dedup: removed {len(to_remove)} duplicate entries by note_id")
        try:
            with _store_lock:
                _save_store_atomically()
        except Exception as e:
            logger.warning(f"Could not save entries_store after dedup: {e}")


def _fix_xhs_timestamps() -> Dict[str, Any]:
    """批量修复 XHS 条目的 published_at：从 explore 页面提取真实发布时间。"""
    import requests as _requests

    xhs_entries = [
        (k, e) for k, e in entries_store.items()
        if e.get("platform") == "xiaohongshu" and e.get("url")
    ]
    if not xhs_entries:
        return {"total": 0, "fixed": 0, "failed": 0}

    # 从 .env 读取 cookie
    cookie_str = ""
    env_path = _root / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("XHS_COOKIES="):
                cookie_str = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                break

    cookie_dict = {}
    for pair in cookie_str.split(";"):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            cookie_dict[k.strip()] = v.strip()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    fixed = 0
    failed = 0
    now_ms = int(_time.time() * 1000)

    for key, entry in xhs_entries:
        url = entry.get("url", "")
        try:
            resp = _requests.get(url, headers=headers, cookies=cookie_dict, timeout=10)
            if resp.status_code != 200:
                failed += 1
                continue

            match = re.search(r'"time"\s*:\s*(\d{13})', resp.text)
            if match:
                ts_ms = int(match.group(1))
                # 排除明显是当前时间的值（±5 分钟）
                if abs(ts_ms - now_ms) > 300_000:
                    dt = datetime.fromtimestamp(ts_ms / 1000)
                    entry["published_at"] = dt
                    fixed += 1
                else:
                    # 备选：从 INITIAL_STATE 中取最老的时间戳
                    state_match = re.search(
                        r'__INITIAL_STATE__\s*=\s*(\{.*?\})\s*</script>', resp.text, re.DOTALL
                    )
                    if state_match:
                        ts_all = re.findall(r'(?<!\d)(\d{13})(?!\d)', state_match.group(1))
                        candidates = [int(t) for t in ts_all if abs(int(t) - now_ms) > 300_000]
                        if candidates:
                            oldest = min(candidates)
                            dt = datetime.fromtimestamp(oldest / 1000)
                            entry["published_at"] = dt
                            fixed += 1
                        else:
                            failed += 1
                    else:
                        failed += 1
            else:
                failed += 1
        except Exception as e:
            logger.debug(f"Fix timestamp failed for {key}: {e}")
            failed += 1

    # 持久化
    if fixed > 0:
        try:
            with _store_lock:
                _save_store_atomically()
        except Exception as e:
            logger.warning(f"Could not save entries_store after timestamp fix: {e}")

    logger.info(f"XHS timestamp fix: {fixed} fixed, {failed} failed out of {len(xhs_entries)}")
    return {"total": len(xhs_entries), "fixed": fixed, "failed": failed}


def _run_pipeline_background(force: bool = False):
    """Run the full pipeline in the background and update latest_result.

    Skips if follow.db hasn't changed since last run (unless force=True).
    """
    global latest_result, pipeline_running, last_run_at, _folo_db_last_mtime

    with _pipeline_lock:
        if pipeline_running:
            logger.info("Pipeline already running, skipping scheduled run")
            return
        pipeline_running = True

    try:
        # Check if FOLO db exists directly at its fixed path
        folo_has_data = _fo_has_db() or any(exports_dir.glob("*.db")) or any(exports_dir.glob("*.json")) or any(exports_dir.glob("*.csv"))
        use_mock = not folo_has_data

        mgr = get_brand_config_manager()
        sources = mgr.get_enabled_weibo_sources() or [
            "https://weibo.com/officialbrand",
            "https://xiaohongshu.com/user/brand",
        ]

        logger.info(f"Background pipeline started (use_mock={use_mock})")
        result = run_full_pipeline(sources=sources, use_mock=use_mock)
        latest_result = result
        last_run_at = datetime.now().isoformat()
        _folo_db_last_mtime = _fo_latest_mtime()
        # 持久化到磁盘，防止进程重启后丢失
        try:
            with open(_RESULT_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(latest_result, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"Could not save latest_result to disk: {e}")
        # 增量合并新条目到 entries_store，已存在条目在新数据有标签时覆盖
        # 过滤：自动剔除只有"教程科普"标签的帖子（纯知识搬运，无商业价值）
        new_updates = result.get("OfficialUpdates", {}).get("updates", [])
        new_updates = [u for u in new_updates if (u.get("engagement_metrics") or {}).get("ai_tags") != ["教程科普"]]
        # 过滤：剔除与口腔护理行业无关的数据
        new_updates = [u for u in new_updates if _is_oral_related(u)]
        added = 0
        updated = 0
        new_entries = []  # 仅本次新增的条目（用于拉取评论）
        for u in new_updates:
            key = f"{u.get('source_url', '')}:{u.get('id', '')}"
            if key and key not in entries_store:
                entries_store[key] = u
                new_entries.append(u)
                added += 1
            elif key:
                # 始终保留已有评论数据（避免重复 API 调用）
                old_em = entries_store[key].get("engagement_metrics") or {}
                new_em = u.get("engagement_metrics") or {}
                if old_em.get("comments"):
                    new_em["comments"] = old_em["comments"]
                if old_em.get("comment_analysis"):
                    new_em["comment_analysis"] = old_em["comment_analysis"]
                # 保留已有 ai_tags（如果新数据没有）
                if old_em.get("ai_tags") and not new_em.get("ai_tags"):
                    new_em["ai_tags"] = old_em["ai_tags"]
                u["engagement_metrics"] = new_em
                entries_store[key] = u
                updated += 1
        logger.info(f"entries_store: +{added} new, +{updated} updated, total {len(entries_store)}")
        try:
            with _store_lock:
                _save_store_atomically()
        except Exception as e:
            logger.warning(f"Could not save entries_store: {e}")
        _retag_missing()
        _purge_clinic_ads()
        _dedup_entries_store()
        # 只对新增条目拉取评论（避免重复调用浪费 API Token）
        token = _read_xhs_api_token()
        if token and new_entries:
            _fetch_and_store_comments(new_entries, token)
        logger.info("Background pipeline finished")
    except Exception as e:
        logger.error(f"Background pipeline failed: {e}", exc_info=True)
    finally:
        with _pipeline_lock:
            pipeline_running = False


_XHS_SEARCH_KEYWORDS = ["牙膏", "牙刷", "电动牙刷", "口腔健康", "牙齿美白"]
_xhs_search_running = False


def _run_xhs_search_background():
    """定时自动搜索小红书关键词。"""
    global _xhs_search_running
    if _xhs_search_running:
        logger.info("XHS search already running, skipping")
        return
    _xhs_search_running = True
    try:
        token = _read_xhs_api_token()
        if not token:
            logger.warning("XHS_API_TOKEN not configured, skipping auto search")
            return

        import os
        _monitor_targets_raw = os.environ.get("XHS_MONITOR_TARGETS", "[]")
        try:
            _monitor_targets = json.loads(_monitor_targets_raw)
        except json.JSONDecodeError:
            _monitor_targets = []

        from src.agents.searcher.xiaohongshu_updates_agent import XiaohongshuUpdatesAgent
        agent = XiaohongshuUpdatesAgent({
            "xhs_api_token": token,
            "xhs_monitor_targets": _monitor_targets,
            "lookback_hours": 720,
        })

        # 加载已有去重集
        for k in entries_store:
            note_id = k.rsplit(":", 1)[-1]
            agent.processed_updates.add(note_id)

        logger.info(f"Auto XHS search started: {_XHS_SEARCH_KEYWORDS}")
        updates = agent.search_by_keywords(_XHS_SEARCH_KEYWORDS, 20)

        # 评分
        agent.apply_scores(updates)

        # 过滤
        updates = [u for u in updates if not ((u.engagement_metrics or {}).get("ai_tags") == ["教程科普"])]
        updates_dict = [u.model_dump() if hasattr(u, 'model_dump') else vars(u) for u in updates]
        updates = [u for u, d in zip(updates, updates_dict)
                   if _is_oral_related(d) and not _is_clinic_ad(d)]

        # 增量合并
        total_saved = 0
        new_entries = []
        for u in updates:
            key = f"{u.source_url}:{u.id}"
            if key not in entries_store:
                entry_dict = u.model_dump() if hasattr(u, 'model_dump') else vars(u)
                entries_store[key] = entry_dict
                new_entries.append(entry_dict)
                total_saved += 1

        logger.info(f"Auto XHS search done: saved {total_saved} new entries, total {len(entries_store)}")

        # 持久化
        if total_saved > 0:
            try:
                with _store_lock:
                    _save_store_atomically()
            except Exception as e:
                logger.warning(f"Could not save entries_store after auto search: {e}")
            _retag_missing()

        # 只对新增条目拉取评论（避免重复调用浪费 API Token）
        if new_entries:
            _fetch_and_store_comments(new_entries, token)
    except Exception as e:
        logger.error(f"Auto XHS search failed: {e}", exc_info=True)
    finally:
        _xhs_search_running = False


def _watch_folo_files():
    """监听 FOLO 目录下 .db 文件变化，文件修改后自动触发 pipeline。"""
    if not FOLO_DIR.exists():
        logger.warning(f"FOLO directory not found: {FOLO_DIR}, file watcher disabled")
        return

    def _loop():
        global _folo_db_last_mtime
        _folo_db_last_mtime = _fo_latest_mtime()
        logger.info(f"FOLO file watcher started — monitoring {FOLO_DIR} (*.db)")
        for changes in _watch_files(FOLO_DIR, watch_filter=lambda change, path: path.endswith(".db")):
            new_mtime = _fo_latest_mtime()
            if new_mtime <= _folo_db_last_mtime:
                continue  # mtime 没变，跳过
            logger.info(f"FOLO .db file changed (mtime {_folo_db_last_mtime} → {new_mtime}), triggering pipeline")
            _folo_db_last_mtime = new_mtime
            if not pipeline_running:
                _run_pipeline_background(force=True)
            else:
                logger.info("Pipeline already running, FOLO change will be picked up next run")

    t = threading.Thread(target=_loop, daemon=True, name="folo-watcher")
    t.start()


@app.on_event("startup")
async def _startup():
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _retag_missing)
    loop.run_in_executor(None, _purge_clinic_ads)
    loop.run_in_executor(None, _dedup_entries_store)
    if _HAS_WATCHFILES:
        loop.run_in_executor(None, _watch_folo_files)
    if not _HAS_APSCHEDULER:
        return
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_run_pipeline_background, "interval", minutes=360, id="auto_pipeline", next_run_time=None)
    scheduler.add_job(_run_xhs_search_background, "interval", minutes=1440, id="auto_xhs_search", next_run_time=None)
    scheduler.start()
    logger.info("APScheduler started — pipeline + XHS search will auto-run every 6 hours")

# ── State ──

exports_dir = _root / "data" / "exports"
FOLO_DIR = Path("D:/wmz/FOLO")  # FOLO 数据库导出目录
_RESULT_CACHE_PATH = _root / "data" / "latest_result.json"

# Ensure directories exist
exports_dir.mkdir(parents=True, exist_ok=True)
(_root / "data" / "exports").mkdir(parents=True, exist_ok=True)

pipeline_running = False
last_run_at: str = ""
_folo_db_last_mtime: float = 0.0  # FOLO 目录下所有 .db 文件最大 mtime，用于变更检测


def _fo_latest_mtime() -> float:
    """Return the latest mtime across all .db files in FOLO_DIR."""
    if not FOLO_DIR.exists():
        return 0.0
    mtimes = [f.stat().st_mtime for f in FOLO_DIR.glob("*.db")]
    return max(mtimes) if mtimes else 0.0


def _fo_has_db() -> bool:
    """Return True if any .db file exists in FOLO_DIR."""
    return FOLO_DIR.exists() and any(FOLO_DIR.glob("*.db"))

# 启动时从磁盘恢复上次 pipeline 结果，防止进程重启后丢失
latest_result: Dict[str, Any] = {}
if _RESULT_CACHE_PATH.exists():
    try:
        with open(_RESULT_CACHE_PATH, "r", encoding="utf-8") as _f:
            latest_result = json.load(_f)
        logger.info(f"Restored latest_result from {_RESULT_CACHE_PATH}")
    except Exception as _e:
        logger.warning(f"Could not restore latest_result: {_e}")

# 持久化条目仓库：key="{source_url}:{id}"，跨 pipeline 运行增量累积，重复条目自动跳过
_STORE_PATH = _root / "data" / "entries_store.json"
entries_store: Dict[str, Any] = {}
if _STORE_PATH.exists():
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as _f:
            _store_list = json.load(_f)
        for _u in _store_list:
            _k = f"{_u.get('source_url', '')}:{_u.get('id', '')}"
            if _k:
                entries_store[_k] = _u
        logger.info(f"Restored {len(entries_store)} entries from store")
    except Exception as _e:
        logger.warning(f"Could not restore entries_store: {_e}")


def _save_store_atomically():
    """原子写入 entries_store 到磁盘，防止并发写损坏文件。"""
    import time as _t
    _tmp = str(_STORE_PATH) + ".tmp"
    try:
        with open(_tmp, "w", encoding="utf-8") as f:
            json.dump(list(entries_store.values()), f, ensure_ascii=False, default=str)
        # Windows 上 os.replace 可能因目标文件被读取而失败，加重试
        for _attempt in range(3):
            try:
                os.replace(_tmp, str(_STORE_PATH))
                return
            except OSError:
                if _attempt < 2:
                    _t.sleep(0.2)
                else:
                    raise
    except Exception:
        if os.path.exists(_tmp):
            try:
                os.remove(_tmp)
            except OSError:
                pass
        raise


# ── Static Files ──

frontend_dir = _root / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="frontend")


# ── Report Engine API ──

@app.get("/api/report/status")
async def report_status():
    """获取报告引擎状态。"""
    from src.report_engine.report_generator import get_report_generator
    gen = get_report_generator()
    return gen.get_status()


@app.get("/api/report/templates")
async def report_templates():
    """获取可用报告模板列表。"""
    from src.report_engine.report_generator import get_report_generator
    gen = get_report_generator()
    return {"templates": gen.get_templates()}


@app.post("/api/report/generate")
async def report_generate(request: Request):
    """启动报告生成任务。"""
    from src.report_engine.report_generator import get_report_generator
    gen = get_report_generator()
    try:
        body = await request.json()
    except Exception:
        body = {}
    query = body.get("query", "口腔护理行业品牌监测报告")
    days = int(body.get("days", 30))
    template_name = body.get("template")
    try:
        task_id = gen.start_report(entries_store, query=query, days=days, template_name=template_name)
        return {"task_id": task_id, "status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/report/progress/{task_id}")
async def report_progress(task_id: str):
    """查询报告生成进度。"""
    from src.report_engine.report_generator import get_report_generator
    gen = get_report_generator()
    task = gen.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@app.get("/api/report/result/{task_id}")
async def report_result(task_id: str):
    """获取报告 HTML 内容。"""
    from src.report_engine.report_generator import get_report_generator
    gen = get_report_generator()
    html = gen.get_task_html(task_id)
    if html is None:
        task = gen.get_task(task_id)
        if task and task.status == "failed":
            raise HTTPException(status_code=500, detail=task.error or "Generation failed")
        if task and task.status == "running":
            raise HTTPException(status_code=202, detail="Still generating")
        raise HTTPException(status_code=404, detail="Task not found or not completed")
    return HTMLResponse(content=html)


# ── Page Routes ──

PAGE_NAMES = ["login", "competitor", "culture", "voc", "report", "settings", "weibo"]

@app.get("/")
async def index():
    """Serve the dashboard."""
    return _serve_html("index")


@app.get("/login")
async def login_page():
    return _serve_html("login")


@app.get("/{page}")
async def serve_page(page: str):
    # 只允许字母、数字、连字符、下划线
    if not re.match(r'^[a-zA-Z0-9_-]+$', page):
        return HTMLResponse("<h1>404 Not Found</h1>", status_code=404)
    if page in PAGE_NAMES:
        return _serve_html(page)
    # Redirect unknown pages to index
    return _serve_html("index")


def _serve_html(name: str) -> HTMLResponse:
    """Read an HTML file from frontend and serve it."""
    path = frontend_dir / f"{name}.html"
    if not path.exists():
        return HTMLResponse(f"<h1>404</h1><p>{name}.html not found</p>", status_code=404)
    return HTMLResponse(path.read_text(encoding="utf-8"))


# ── API Routes ──


@app.get("/api/status")
async def status():
    """Server health check."""
    return {
        "status": "ok",
        "pipeline_running": pipeline_running,
        "has_latest_result": bool(latest_result),
        "exports_count": len(list(exports_dir.glob("*"))),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/agents")
async def get_agents():
    """Return all agent definitions with their input/output contracts."""
    return {
        "groups": [
            {
                "id": "searcher",
                "name": "Searcher 搜索者",
                "description": "多渠道数据采集与标准化",
                "agents": [
                    {"id": "OfficialUpdatesAgent", "inputs": ["sources"], "outputs": ["OfficialUpdates"], "description": "监控官方品牌账号更新"},
                    {"id": "BrandCultureListeningAgent", "inputs": ["brandId", "sources", "frequency"], "outputs": ["BrandCultureEvents"], "description": "监听品牌文化讨论"},
                    {"id": "SocialMediaFeedbackAgent", "inputs": ["sources"], "outputs": ["SocialMediaFeedback"], "description": "采集社交媒体反馈"},
                    {"id": "ShoppingPlatformFeedbackAgent", "inputs": ["platforms"], "outputs": ["ShoppingFeedback"], "description": "收集电商平台评价"},
                ]
            },
            {
                "id": "analyst",
                "name": "Analyst 分析师",
                "description": "数据分析与洞察提取",
                "agents": [
                    {"id": "OtherBrandCampaignAnalystAgent", "inputs": ["CompetitionData", "BrandCultureEvent", "SocialMediaFeedback"], "outputs": ["CompetitorCampaignAnalysis"], "description": "分析竞品营销活动"},
                    {"id": "UserFeedbackAnalystAgent", "inputs": ["ShoppingFeedback", "SocialMediaFeedback"], "outputs": ["UserFeedbackInsights"], "description": "提取用户反馈洞察"},
                ]
            },
            {
                "id": "reporter",
                "name": "Reporter 报告员",
                "description": "多格式报告生成",
                "agents": [
                    {"id": "TemplateDrivenReportAgent", "inputs": ["AnalysisResults", "Insights", "SelectedTemplate"], "outputs": ["Reports"], "description": "生成 Markdown/JSON 报告"},
                ]
            },
            {
                "id": "supervisor",
                "name": "Supervisor 主管",
                "description": "任务调度与资源管理",
                "agents": [
                    {"id": "TaskDispatcherAgent", "inputs": ["PendingTasks", "ResourceAvailability"], "outputs": ["AssignmentPlan"], "description": "按优先级分派任务"},
                ]
            },
        ],
        "data_flow": "Searcher → Analyst → Reporter → Supervisor",
    }


# ── Brand Config API ──


@app.get("/api/brands")
async def list_brands():
    """List all brand configurations."""
    mgr = get_brand_config_manager()
    brands = mgr.list_brands()
    return {"brands": [b.model_dump() for b in brands], "count": len(brands)}


@app.post("/api/brands")
async def add_brand(brand: BrandConfig):
    """Add a new brand configuration."""
    mgr = get_brand_config_manager()
    try:
        result = mgr.add_brand(brand)
        return {"success": True, "brand": result.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.put("/api/brands/{brand_id}")
async def update_brand(brand_id: str, updates: dict):
    """Update an existing brand configuration."""
    mgr = get_brand_config_manager()
    result = mgr.update_brand(brand_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found")
    return {"success": True, "brand": result.model_dump()}


@app.delete("/api/brands/{brand_id}")
async def delete_brand(brand_id: str):
    """Delete a brand configuration."""
    mgr = get_brand_config_manager()
    if not mgr.delete_brand(brand_id):
        raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found")
    return {"success": True}


@app.get("/api/brands/sources")
async def get_brand_sources():
    """Get enabled Weibo source URLs for pipeline input."""
    mgr = get_brand_config_manager()
    sources = mgr.get_enabled_weibo_sources()
    return {"sources": sources, "count": len(sources)}


# ── Pipeline API ──


@app.post("/api/pipeline/run")
async def run_pipeline(background_tasks: BackgroundTasks):
    """Execute the full LangGraph pipeline."""
    if pipeline_running:
        raise HTTPException(status_code=409, detail="Pipeline is already running")

    background_tasks.add_task(_run_pipeline_background, True)
    return {"success": True, "message": "Pipeline started in background", "timestamp": datetime.now().isoformat()}


@app.post("/api/xhs/search/run")
async def run_xhs_search(background_tasks: BackgroundTasks):
    """手动触发小红书搜索（含固定博主监听）。"""
    if _xhs_search_running:
        raise HTTPException(status_code=409, detail="XHS search is already running")
    background_tasks.add_task(_run_xhs_search_background)
    return {"success": True, "message": "XHS search started in background"}


@app.get("/api/pipeline/status")
async def pipeline_status():
    """Return pipeline running state and last run timestamp."""
    return {
        "running": pipeline_running,
        "last_run_at": last_run_at,
        "entry_count": len(entries_store),
    }


_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")


def _sanitize(obj):
    """递归清理字符串中的非法 surrogate 字符（导致 JSON 序列化失败）。"""
    if isinstance(obj, str):
        return _SURROGATE_RE.sub("", obj)
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


@app.get("/api/data/latest")
async def get_latest_data():
    """Return all accumulated entries from entries_store."""
    if not entries_store:
        return {
            "has_data": False,
            "message": "No pipeline run yet. POST /api/pipeline/run to execute.",
            "data": {},
        }
    updates = []
    for v in entries_store.values():
        entry = {k: val for k, val in v.items() if k != "raw_data"}
        updates.append(_sanitize(entry))
    return {
        "has_data": True,
        "timestamp": datetime.now().isoformat(),
        "summary": {"OfficialUpdates": f"{len(updates)} 条历史记录"},
        "data": {"OfficialUpdates": {"updates": updates}},
    }


@app.delete("/api/entries/clear")
async def clear_entries():
    """Clear all accumulated entries (use when you want a full refresh)."""
    entries_store.clear()
    if _STORE_PATH.exists():
        _STORE_PATH.unlink()
    return {"success": True, "message": "entries_store cleared"}


def _extract_brand_name(entry: dict) -> str:
    raw = ((entry.get('engagement_metrics') or {}).get('feed_title')
           or (entry.get('engagement_metrics') or {}).get('nickname')
           or (entry.get('engagement_metrics') or {}).get('author')
           or '')
    name = re.sub(r'[\s]*(的)?[\s]*(微博|bilibili|b站|小红书|抖音|快手|微信)[\s]*(动态|笔记|视频)?', '', raw, flags=re.I).strip()
    from src.agents.analyst.competitor_insight_agent import _normalize_brand
    return _normalize_brand(name)


def _filter_entries_by_days(entries, days: int):
    if not days or days <= 0:
        return entries
    cutoff = datetime.now() - timedelta(days=days)
    filtered = []
    for e in entries:
        pub = e.get('published_at', '')
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace('Z', '+00:00'))
                if dt >= cutoff:
                    filtered.append(e)
            except (ValueError, TypeError):
                filtered.append(e)
        else:
            filtered.append(e)
    return filtered


@app.get("/api/entries/stats")
async def entries_stats(days: int = 30, platform: str = ""):
    """Aggregate statistics from entries_store."""
    entries = list(entries_store.values())
    if days > 0:
        entries = _filter_entries_by_days(entries, days)
    if platform:
        entries = [e for e in entries if e.get('platform') == platform]

    total = len(entries)
    by_platform = dict(Counter(e.get('platform', 'unknown') for e in entries))
    by_update_type = dict(Counter(e.get('update_type', 'brand_content') for e in entries))

    # Top tags
    all_tags = []
    for e in entries:
        tags = (e.get('engagement_metrics') or {}).get('ai_tags', [])
        all_tags.extend(t for t in tags if t != '品牌联动')
    top_tags = [{"tag": t, "count": c} for t, c in Counter(all_tags).most_common(20)]

    # Entries per day
    day_counts = defaultdict(int)
    for e in entries:
        pub = e.get('published_at', '')
        if pub:
            try:
                d = datetime.fromisoformat(pub.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                day_counts[d] += 1
            except (ValueError, TypeError):
                pass
    entries_per_day = [{"date": d, "count": c} for d, c in sorted(day_counts.items())]

    # Top brands
    brand_counts = Counter(_extract_brand_name(e) for e in entries)
    brand_counts.pop('', None)
    top_brands = [{"brand": b, "count": c} for b, c in brand_counts.most_common(15)]

    # Date range
    dates = []
    for e in entries:
        pub = e.get('published_at', '')
        if pub:
            try:
                dates.append(datetime.fromisoformat(pub.replace('Z', '+00:00')))
            except (ValueError, TypeError):
                pass
    date_range = {}
    if dates:
        date_range = {"from": min(dates).strftime('%Y-%m-%d'), "to": max(dates).strftime('%Y-%m-%d')}

    return {
        "total_entries": total,
        "by_platform": by_platform,
        "by_update_type": by_update_type,
        "top_tags": top_tags,
        "entries_per_day": entries_per_day,
        "top_brands": top_brands,
        "date_range": date_range,
    }


@app.get("/api/entries/keyword-cloud")
async def entries_keyword_cloud(days: int = 30, limit: int = 50):
    """Keyword frequency for word cloud visualization."""
    entries = list(entries_store.values())
    if days > 0:
        entries = _filter_entries_by_days(entries, days)
    all_tags = []
    for e in entries:
        tags = (e.get('engagement_metrics') or {}).get('ai_tags', [])
        all_tags.extend(t for t in tags if t != '品牌联动')
    keywords = [{"text": t, "value": c} for t, c in Counter(all_tags).most_common(limit)]
    return {"keywords": keywords}


@app.get("/api/entries/feed")
async def entries_feed(
    page: int = 1,
    per_page: int = 20,
    platform: str = "",
    update_type: str = "",
    days: int = 0,
    keyword: str = "",
):
    """Paginated entry feed with optional filters."""
    entries = list(entries_store.values())
    if days > 0:
        entries = _filter_entries_by_days(entries, days)
    if platform:
        entries = [e for e in entries if e.get('platform') == platform]
    if update_type:
        entries = [e for e in entries if e.get('update_type') == update_type]
    if keyword:
        keyword_lower = keyword.lower()
        entries = [e for e in entries
                   if keyword_lower in (e.get('title', '') or '').lower()
                   or keyword_lower in (e.get('content', '') or '').lower()]

    # Sort by published_at desc
    def _sort_key(e):
        pub = e.get('published_at', '')
        try:
            return datetime.fromisoformat(pub.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return datetime.min
    entries.sort(key=_sort_key, reverse=True)

    total = len(entries)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    page_entries = entries[start:start + per_page]

    # Slim down entries for feed (remove raw_data to reduce payload)
    slim = []
    for e in page_entries:
        d = {k: v for k, v in e.items() if k != 'raw_data'}
        slim.append(d)

    return {"entries": slim, "total": total, "page": page, "per_page": per_page, "pages": pages}


@app.get("/api/insights/competitor")
async def competitor_insights(brand: str = ""):
    """Generate competitive insights from entries_store."""
    from src.agents.analyst.competitor_insight_agent import analyze
    entries = list(entries_store.values())
    if not entries:
        return {"error": "No data available. Run pipeline first."}
    result = analyze(entries, target_brand=brand or None)
    return result


# ── XHS Keyword Search API ──


def _read_xhs_api_token() -> str:
    """从 .env 读取 XHS_API_TOKEN。"""
    env_path = _root / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("XHS_API_TOKEN="):
                val = line.strip().split("=", 1)[1].strip()
                return val.strip('"').strip("'")
    return ""


@app.get("/api/xhs/analysis")
async def xhs_analysis(days: int = 30):
    """分析关键词搜索结果的价值分布和宣发效果。"""
    def _parse_int(v, default=0):
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return default
        return default

    # 筛选关键词搜索结果
    keyword_entries = []
    for e in entries_store.values():
        src = e.get("source_url", "")
        if "xhs:keyword:" not in src:
            continue
        if days > 0:
            filtered = _filter_entries_by_days([e], days)
            if not filtered:
                continue
        keyword_entries.append(e)

    total = len(keyword_entries)

    # 价值分级分布
    tier_counts = {"S": 0, "A": 0, "B": 0, "C": 0}
    for e in keyword_entries:
        tier = (e.get("engagement_metrics") or {}).get("value_tier", "C")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    # Top 10 高价值帖子
    scored = [(e, (e.get("engagement_metrics") or {}).get("value_score", 0)) for e in keyword_entries]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_posts = []
    for e, score in scored[:10]:
        top_posts.append({
            "id": e.get("id"),
            "title": e.get("title", "")[:80],
            "value_score": score,
            "value_tier": (e.get("engagement_metrics") or {}).get("value_tier", "C"),
            "content_type": (e.get("engagement_metrics") or {}).get("content_type", "general"),
            "url": e.get("url", ""),
            "published_at": e.get("published_at", ""),
            "liked_count": (e.get("engagement_metrics") or {}).get("liked_count", 0),
            "comment_count": (e.get("engagement_metrics") or {}).get("comment_count", 0),
        })

    # 宣发手法效果分析（按 ai_tags 分组，计算平均互动值）
    tag_engagement = defaultdict(lambda: {"count": 0, "total_engagement": 0})
    for e in keyword_entries:
        em = e.get("engagement_metrics") or {}
        ai_tags = em.get("ai_tags", [])
        engagement = (
            _parse_int(em.get("liked_count", 0))
            + _parse_int(em.get("comment_count", 0)) * 3
            + _parse_int(em.get("collected_count", 0)) * 2
            + _parse_int(em.get("share_count", 0)) * 2
        )
        for tag in ai_tags:
            if tag == "品牌联动":
                continue
            tag_engagement[tag]["count"] += 1
            tag_engagement[tag]["total_engagement"] += engagement

    promo_effectiveness = []
    for tag, data in tag_engagement.items():
        avg = data["total_engagement"] // max(data["count"], 1)
        promo_effectiveness.append({
            "tag": tag,
            "count": data["count"],
            "avg_engagement": avg,
        })
    promo_effectiveness.sort(key=lambda x: x["avg_engagement"], reverse=True)

    # 各关键词统计
    kw_stats = defaultdict(lambda: {"total": 0, "S": 0, "A": 0, "B": 0, "C": 0})
    for e in keyword_entries:
        src = e.get("source_url", "")
        kw = src.replace("xhs:keyword:", "")
        tier = (e.get("engagement_metrics") or {}).get("value_tier", "C")
        kw_stats[kw]["total"] += 1
        kw_stats[kw][tier] = kw_stats[kw].get(tier, 0) + 1
    keyword_stats = [{"keyword": k, **v} for k, v in kw_stats.items()]

    return {
        "total_searched": total,
        "by_value_tier": tier_counts,
        "top_posts": top_posts,
        "promo_effectiveness": promo_effectiveness[:15],
        "keyword_stats": keyword_stats,
    }


def _fetch_and_store_comments(entries: list, token: str):
    """批量拉取评论并存入 entries_store（同步函数，应在后台线程执行）。

    省钱策略：
    - 仅拉取近30天帖子（旧帖子评论不再变化）
    - 跳过低互动帖子（点赞<10）
    - 每篇最多2页（20条评论，覆盖90%场景）
    - 每次运行最多处理50条
    - 已有评论的帖子跳过
    """
    from src.agents.searcher.xhs_api.note_comments import XHSNoteComments
    from src.agents.searcher.comment_analyzer import analyze_comments

    crawler = XHSNoteComments(token)
    fetched = 0
    max_per_run = 50
    thirty_days_ago = datetime.now() - timedelta(days=30)

    for entry in entries:
        if fetched >= max_per_run:
            logger.info(f"Comment fetch: hit max_per_run={max_per_run}, stopping")
            break

        note_id = entry.get("id", "")
        src = entry.get("source_url", "") or ""
        # 处理所有小红书数据（包括关键词搜索）
        if not src.startswith("xhs:"):
            continue
        em = entry.get("engagement_metrics") or {}
        # 已有评论数据则跳过
        if em.get("comments") or em.get("comment_analysis"):
            continue
        # 跳过低互动帖子（点赞<10）
        likes = em.get("liked_count") or em.get("likes") or 0
        if likes < 10:
            # 标记为已处理（空评论），避免下次再检查
            em["comment_analysis"] = {"total_comments": 0, "sentiment": {"positive": 0, "negative": 0, "neutral": 0}, "selling_points": []}
            entry["engagement_metrics"] = em
            key = f"{src}:{note_id}"
            if key in entries_store:
                entries_store[key] = entry
            continue
        # 跳过30天前的帖子
        pub = entry.get("published_at")
        if pub:
            try:
                pub_date = datetime.fromisoformat(pub.replace("Z", "+00:00")).replace(tzinfo=None)
                if pub_date < thirty_days_ago:
                    em["comment_analysis"] = {"total_comments": 0, "sentiment": {"positive": 0, "negative": 0, "neutral": 0}, "selling_points": []}
                    entry["engagement_metrics"] = em
                    key = f"{src}:{note_id}"
                    if key in entries_store:
                        entries_store[key] = entry
                    continue
            except (ValueError, TypeError):
                pass
        try:
            result = crawler.get_all_comments(
                note_id=note_id,
                sort="latest",
                fetch_sub_comments=False,
                delay_seconds=0.2,
                sub_comment_delay=0.1,
                max_pages=1,
            )
            if result and result.get("success"):
                comments = result.get("data", {}).get("comments", [])
                analysis = analyze_comments(comments)
                em["comments"] = comments
                em["comment_analysis"] = analysis
                entry["engagement_metrics"] = em
                # 更新 entries_store
                key = f"{src}:{note_id}"
                if key in entries_store:
                    entries_store[key] = entry
                fetched += 1
        except Exception as e:
            logger.warning(f"Comment fetch failed for {note_id}: {e}")

    if fetched > 0:
        logger.info(f"Fetched comments for {fetched} entries")
        try:
            with _store_lock:
                _save_store_atomically()
        except Exception as e:
            logger.warning(f"Could not save entries_store after comment fetch: {e}")


@app.get("/api/xhs/comments/{note_id}")
async def get_note_comments(note_id: str, sort: str = "latest", force: int = 0):
    """获取小红书笔记评论（含情感分析 + 卖点标签）。优先从本地缓存读取。"""
    # 优先从 entries_store 读取已缓存的评论
    if not force:
        for entry in entries_store.values():
            if entry.get("id") == note_id:
                em = entry.get("engagement_metrics") or {}
                cached_comments = em.get("comments")
                cached_analysis = em.get("comment_analysis")
                if cached_comments is not None:
                    return {
                        "success": True,
                        "note_id": note_id,
                        "comments": cached_comments,
                        "total_comments": len(cached_comments),
                        "analysis": cached_analysis or {},
                        "cached": True,
                    }

    token = _read_xhs_api_token()
    if not token:
        raise HTTPException(status_code=500, detail="XHS_API_TOKEN 未配置")

    from src.agents.searcher.xhs_api.note_comments import XHSNoteComments
    from src.agents.searcher.comment_analyzer import analyze_comments

    import asyncio

    crawler = XHSNoteComments(token)

    try:
        result = await asyncio.to_thread(
            crawler.get_all_comments,
            note_id=note_id,
            sort=sort,
            fetch_sub_comments=False,
            delay_seconds=0.2,
            sub_comment_delay=0.1,
            max_pages=5,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取评论失败: {e}")

    if not result or not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("message", "获取评论失败") if result else "空响应")

    comments_data = result.get("data", {})
    all_comments = comments_data.get("comments", [])

    # 情感分析 + 卖点提取
    analysis = analyze_comments(all_comments)

    # 缓存到 entries_store，下次直接读
    for entry in entries_store.values():
        if entry.get("id") == note_id:
            em = entry.get("engagement_metrics") or {}
            em["comments"] = all_comments
            em["comment_analysis"] = analysis
            entry["engagement_metrics"] = em
            try:
                with _store_lock:
                    _save_store_atomically()
            except Exception:
                pass
            break

    return {
        "success": True,
        "note_id": note_id,
        "comments": all_comments,
        "total_comments": len(all_comments),
        "analysis": analysis,
    }


@app.post("/api/exports/upload")
async def upload_export(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """Upload a Follow/FOLO export file (.db, .json, or .csv)."""
    if not file.filename.endswith((".json", ".csv", ".db")):
        raise HTTPException(status_code=400, detail="Only .db, .json, and .csv files are supported")

    # 防止路径穿越
    safe_name = os.path.basename(file.filename)
    if ".." in safe_name or "/" in safe_name or "\\" in safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = exports_dir / safe_name
    try:
        # 限制上传文件大小为 50MB
        MAX_UPLOAD_SIZE = 50 * 1024 * 1024
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="File too large (max 50MB)")
        file_path.write_bytes(content)
        logger.info(f"Export file uploaded: {safe_name} ({len(content)} bytes)")
        if background_tasks is not None:
            background_tasks.add_task(_run_pipeline_background)
        return {
            "success": True,
            "filename": safe_name,
            "size": len(content),
            "path": str(file_path),
            "pipeline_triggered": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/exports")
async def list_exports():
    """List all FOLO export files in the data/exports directory."""
    files = []
    for f in sorted(exports_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.suffix.lower() in (".json", ".csv", ".db"):
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    return {"files": files, "count": len(files), "directory": str(exports_dir)}


# ── Helpers ──

def _summarize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Create a human-readable summary of pipeline results."""
    summary = {}

    ofu = result.get("OfficialUpdates", {})
    if ofu:
        summary["OfficialUpdates"] = f"{len(ofu.get('updates', []))} 条更新 / {ofu.get('source_count', 0)} 个源"

    bce = result.get("BrandCultureEvents", {})
    if bce:
        events = bce.get("events", [])
        summary["BrandCultureEvents"] = f"{len(events)} 个事件"

    smf = result.get("SocialMediaFeedback", {})
    if smf:
        summary["SocialMediaFeedback"] = f"{len(smf.get('items', []))} 条反馈"

    spf = result.get("ShoppingFeedback", {})
    if spf:
        summary["ShoppingFeedback"] = f"{len(spf.get('items', []))} 条评价"

    cca = result.get("CompetitorCampaignAnalysis", {})
    if cca:
        summary["CompetitorCampaignAnalysis"] = f"{cca.get('total_campaigns_analyzed', 0)} 个活动 / {len(cca.get('competitors', []))} 个竞品"

    ufi = result.get("UserFeedbackInsights", {})
    if ufi:
        summary["UserFeedbackInsights"] = f"{len(ufi.get('trends', []))} 个趋势 / {len(ufi.get('pain_points', []))} 个痛点"

    rpt = result.get("Reports", {})
    if rpt:
        report = rpt.get("report", {})
        summary["Reports"] = report.get("title", "Unknown")

    plan = result.get("AssignmentPlan", {})
    if plan:
        summary["AssignmentPlan"] = f"{plan.get('total_tasks', 0)} 个任务分派"

    return summary


# ── Entry ──

if __name__ == "__main__":
    config = get_api_config()
    print(f"Starting Brand Listener server at http://{config['host']}:{config['port']}")
    print(f"Frontend: http://localhost:{config['port']}")
    print(f"API docs: http://localhost:{config['port']}/docs")
    print(f"FOLO exports directory: {exports_dir}")
    uvicorn.run(
        "server:app",
        host=config["host"],
        port=config["port"],
        reload=config["reload"],
    )
