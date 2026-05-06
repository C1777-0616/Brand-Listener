"""
Brand Listener - FastAPI Web Server

Provides a web interface and REST API for the LangGraph pipeline.
Serves frontend static files and exposes endpoints to trigger/manage the pipeline.
"""
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# Ensure project root is in path
_root = Path(__file__).parent
sys.path.insert(0, str(_root))

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    _HAS_APSCHEDULER = True
except ImportError:
    _HAS_APSCHEDULER = False
    logging.getLogger("server").warning(
        "apscheduler not installed — auto-refresh disabled. Run: pip install apscheduler"
    )

from src.utils.config import get_api_config
from src.brand_config import get_brand_config_manager, BrandConfig
from langgraph.workflow import run_full_pipeline, print_pipeline_result
from src.agents.searcher.content_tagging_agent import ContentTaggingAgent

logger = logging.getLogger("server")

# ── FastAPI App ──

app = FastAPI(title="Brand Listener API", version="0.1.0")

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
            with open(_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(list(entries_store.values()), f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"Could not save entries_store after retag: {e}")


def _run_pipeline_background(force: bool = False):
    """Run the full pipeline in the background and update latest_result.

    Skips if follow.db hasn't changed since last run (unless force=True).
    """
    global latest_result, pipeline_running, last_run_at, _folo_db_last_mtime

    if pipeline_running:
        logger.info("Pipeline already running, skipping scheduled run")
        return

    # 不再因 FOLO .db 未变而跳过整条 pipeline（XHS 等数据源需要始终运行）
    # exporter 层面可通过 entries_store 做去重

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
        new_updates = result.get("OfficialUpdates", {}).get("updates", [])
        added = 0
        updated = 0
        for u in new_updates:
            key = f"{u.get('source_url', '')}:{u.get('id', '')}"
            if key and key not in entries_store:
                entries_store[key] = u
                added += 1
            elif key:
                old_tags = (entries_store[key].get("engagement_metrics") or {}).get("ai_tags")
                new_tags = (u.get("engagement_metrics") or {}).get("ai_tags")
                if new_tags and not old_tags:
                    entries_store[key] = u
                    updated += 1
        logger.info(f"entries_store: +{added} new, +{updated} updated, total {len(entries_store)}")
        logger.info(f"entries_store: +{added} new, total {len(entries_store)}")
        try:
            with open(_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(list(entries_store.values()), f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"Could not save entries_store: {e}")
        _retag_missing()
        logger.info("Background pipeline finished")
    except Exception as e:
        logger.error(f"Background pipeline failed: {e}", exc_info=True)
    finally:
        pipeline_running = False


@app.on_event("startup")
async def _startup():
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _retag_missing)
    if not _HAS_APSCHEDULER:
        return
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_run_pipeline_background, "interval", minutes=15, id="auto_pipeline")
    scheduler.start()
    logger.info("APScheduler started — pipeline will auto-run every 15 minutes")

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

# ── Static Files ──

frontend_dir = _root / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="frontend")


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
    if page in PAGE_NAMES:
        return _serve_html(page)
    if "." in page:
        return HTMLResponse("<h1>404 Not Found</h1>", status_code=404)
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


@app.get("/api/pipeline/status")
async def pipeline_status():
    """Return pipeline running state and last run timestamp."""
    return {
        "running": pipeline_running,
        "last_run_at": last_run_at,
        "entry_count": len(entries_store),
    }


@app.get("/api/data/latest")
async def get_latest_data():
    """Return all accumulated entries from entries_store."""
    if not entries_store:
        return {
            "has_data": False,
            "message": "No pipeline run yet. POST /api/pipeline/run to execute.",
            "data": {},
        }
    updates = list(entries_store.values())
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


@app.get("/api/insights/competitor")
async def competitor_insights(brand: str = ""):
    """Generate competitive insights from entries_store."""
    from src.agents.analyst.competitor_insight_agent import analyze
    entries = list(entries_store.values())
    if not entries:
        return {"error": "No data available. Run pipeline first."}
    result = analyze(entries, target_brand=brand or None)
    return result


@app.post("/api/exports/upload")
async def upload_export(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """Upload a Follow/FOLO export file (.db, .json, or .csv)."""
    if not file.filename.endswith((".json", ".csv", ".db")):
        raise HTTPException(status_code=400, detail="Only .db, .json, and .csv files are supported")

    file_path = exports_dir / file.filename
    try:
        content = await file.read()
        file_path.write_bytes(content)
        logger.info(f"Export file uploaded: {file.filename} ({len(content)} bytes)")
        if background_tasks is not None:
            background_tasks.add_task(_run_pipeline_background)
        return {
            "success": True,
            "filename": file.filename,
            "size": len(content),
            "path": str(file_path),
            "pipeline_triggered": True,
        }
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
