import json
import os
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from loguru import logger

from apis.xhs_pc_apis import XHS_Apis
from main import Data_Spider
from xhs_utils.common_util import init
from xhs_utils.data_util import save_to_xlsx, handle_note_info


TARGETS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "monitor_targets.json"))
STATE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "datas", "monitor_state.json"))


def ensure_parent_dir(file_path: str):
    parent = os.path.dirname(file_path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent)


def load_json(file_path: str, default_value):
    if not os.path.exists(file_path):
        return default_value
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(file_path: str, data):
    ensure_parent_dir(file_path)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_target(target: dict):
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


def normalize_note_from_list_item(note: dict, note_url: str):
    note_data = dict(note)
    if "id" not in note_data and note_data.get("note_id"):
        note_data["id"] = note_data["note_id"]
    note_data["url"] = note_url
    try:
        return handle_note_info(note_data)
    except Exception:
        return None


def run_monitor():
    cookies_str, base_path = init()
    api = XHS_Apis()
    spider = Data_Spider()
    targets_config = load_json(TARGETS_FILE, {"targets": []})
    state = load_json(STATE_FILE, {"targets": {}})
    targets = targets_config.get("targets", [])

    if not targets:
        logger.warning(f"未找到监听目标，请先填写配置文件: {TARGETS_FILE}")
        return

    for target in targets:
        if not target.get("enabled", True):
            continue
        name = (target.get("name") or target.get("user_id") or target.get("user_url") or "unknown").strip()
        user_id, xsec_token, xsec_source = parse_target(target)
        if not user_id:
            logger.warning(f"[{name}] 跳过：未解析到 user_id")
            continue

        target_key = f"{user_id}"
        target_state = state["targets"].get(target_key, {"seen_note_ids": []})
        seen_note_ids = set(target_state.get("seen_note_ids", []))

        success, msg, res_json = api.get_user_note_info(
            user_id=user_id,
            cursor="",
            cookies_str=cookies_str,
            xsec_token=xsec_token,
            xsec_source=xsec_source,
            proxies=None,
        )
        if not success:
            logger.warning(f"[{name}] 获取最新笔记失败: {msg}")
            continue

        notes = res_json.get("data", {}).get("notes", [])
        if not notes:
            logger.info(f"[{name}] 当前无可用笔记")
            continue

        new_note_items = []
        for note in notes:
            note_id = note.get("note_id") or note.get("id")
            note_token = note.get("xsec_token") or xsec_token
            if not note_id or not note_token:
                continue
            if note_id in seen_note_ids:
                continue
            note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={note_token}&xsec_source={xsec_source}"
            new_note_items.append((note_id, note, note_url))

        if not new_note_items:
            logger.info(f"[{name}] 无新笔记")
            target_state["last_check_at"] = datetime.now().isoformat(timespec="seconds")
            state["targets"][target_key] = target_state
            continue

        logger.info(f"[{name}] 检测到新笔记 {len(new_note_items)} 条，开始抓取详情")
        note_infos = []
        success_note_ids = []
        for note_id, simple_note, note_url in new_note_items:
            detail_success, detail_msg, note_info = spider.spider_note(note_url, cookies_str, proxies=None)
            if detail_success and note_info is not None:
                note_infos.append(note_info)
                success_note_ids.append(note_id)
                continue
            fallback_note_info = normalize_note_from_list_item(simple_note, note_url)
            if fallback_note_info is not None:
                note_infos.append(fallback_note_info)
                success_note_ids.append(note_id)
            else:
                logger.warning(f"[{name}] 笔记解析失败，note_id={note_id}, msg={detail_msg}")

        if note_infos:
            excel_name = f"monitor_{name}_{user_id}"
            excel_path = os.path.abspath(os.path.join(base_path["excel"], f"{excel_name}.xlsx"))
            if os.path.exists(excel_path):
                old_data = load_json(
                    os.path.abspath(os.path.join(base_path["excel"], f"{excel_name}.json")),
                    [],
                )
            else:
                old_data = []
            merged_data = note_infos + old_data
            save_to_xlsx(merged_data, excel_path)
            save_json(
                os.path.abspath(os.path.join(base_path["excel"], f"{excel_name}.json")),
                merged_data,
            )
            logger.info(f"[{name}] 新增导出 {len(note_infos)} 条")

        updated_seen = list(seen_note_ids.union(set(success_note_ids)))
        target_state["seen_note_ids"] = updated_seen[-3000:]
        target_state["last_check_at"] = datetime.now().isoformat(timespec="seconds")
        state["targets"][target_key] = target_state

    save_json(STATE_FILE, state)
    logger.info("本轮监听结束")


if __name__ == "__main__":
    run_monitor()

