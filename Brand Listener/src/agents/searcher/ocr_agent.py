"""
OCRAgent - 从图片/视频封面中 OCR 提取品牌/产品名称。

使用 EasyOCR（中文+英文）识别图片文字，匹配品牌/产品关键词。
在 ContentTaggingAgent 之后运行，为每条帖子的 engagement_metrics 添加 ocr_analysis 字段。
与文本分析组成双线筛选：文本没提到品牌但图片中有品牌名的帖子也能被识别。
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.agents.searcher.keyword_dicts import match_keywords


class OCRAgent:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_images = config.get("ocr_max_images", 3)
        self.timeout_seconds = config.get("ocr_timeout_seconds", 60)
        self.enabled = config.get("ocr_enabled", True)
        self._ocr_engine = None

    def _get_ocr_engine(self):
        """懒加载 EasyOCR 单例。"""
        if self._ocr_engine is None:
            try:
                import easyocr
                self._ocr_engine = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
                logger.info("OCRAgent: EasyOCR engine initialized")
            except ImportError:
                logger.warning("OCRAgent: easyocr not installed, OCR disabled")
                self.enabled = False
                return None
            except Exception as e:
                logger.warning(f"OCRAgent: EasyOCR init failed: {e}")
                self.enabled = False
                return None
        return self._ocr_engine

    def _download_image(self, url: str) -> Optional[Any]:
        """下载图片并返回 numpy array。失败返回 None。"""
        try:
            import cv2
            import numpy as np

            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            img_array = np.frombuffer(resp.content, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            logger.debug(f"OCRAgent: image download failed {url[:80]}: {e}")
            return None

    def _ocr_image(self, img_array) -> str:
        """对图片运行 OCR，返回识别出的文字。"""
        engine = self._get_ocr_engine()
        if engine is None:
            return ""
        try:
            result = engine.readtext(img_array)
            texts = []
            for detection in result:
                # EasyOCR returns [bbox, text, confidence]
                if len(detection) >= 3:
                    text = detection[1]
                    confidence = detection[2]
                    if confidence > 0.5:
                        texts.append(text)
                elif len(detection) >= 2:
                    texts.append(detection[1])
            return " ".join(texts)
        except Exception as e:
            logger.debug(f"OCRAgent: OCR failed: {e}")
            return ""

    def _extract_image_urls(self, entry: Dict) -> List[str]:
        """从 entry 提取图片 URL 列表（最多 max_images 张）。"""
        urls = []
        media = entry.get("media_urls") or []
        for url in media:
            if url and not self._is_video_url(url):
                urls.append(url)
            if len(urls) >= self.max_images:
                return urls

        # 如果没有 media_urls 但有 thumbnail_url（视频封面）
        if not urls:
            thumb = entry.get("thumbnail_url")
            if thumb:
                urls.append(thumb)

        # 最后尝试 raw_data 中的 image_list
        if not urls:
            raw = entry.get("raw_data") or {}
            if isinstance(raw, dict):
                image_list = raw.get("image_list") or []
                for img in image_list:
                    if isinstance(img, dict):
                        info = img.get("info_list") or []
                        if len(info) >= 2:
                            urls.append(info[1].get("url", ""))
                    elif isinstance(img, str):
                        urls.append(img)
                    if len(urls) >= self.max_images:
                        break

        return urls[:self.max_images]

    @staticmethod
    def _is_video_url(url: str) -> bool:
        """判断 URL 是否为视频文件。"""
        video_exts = ('.mp4', '.mov', '.avi', '.flv', '.webm', '.m3u8')
        url_lower = url.lower()
        return any(url_lower.endswith(ext) for ext in video_exts) or 'sns-video' in url_lower

    def process_entry(self, entry: Dict) -> Dict:
        """处理单条帖子：下载图片→OCR→匹配关键词。

        将结果写入 entry["engagement_metrics"]["ocr_analysis"]。
        返回 ocr_analysis dict。
        """
        em = entry.setdefault("engagement_metrics", {})

        # 已处理过则跳过
        if em.get("ocr_analysis"):
            return em["ocr_analysis"]

        image_urls = self._extract_image_urls(entry)
        if not image_urls:
            result = {"brands": [], "products": [], "ingredients": [],
                      "raw_texts": [], "image_count": 0,
                      "processed_at": datetime.now().isoformat()}
            em["ocr_analysis"] = result
            return result

        all_texts = []
        for url in image_urls:
            img = self._download_image(url)
            if img is not None:
                text = self._ocr_image(img)
                if text.strip():
                    all_texts.append(text.strip())

        # 合并所有 OCR 文字进行关键词匹配
        combined_text = " ".join(all_texts)
        matched = match_keywords(combined_text) if combined_text else {
            "brands": [], "products": [], "ingredients": []
        }

        result = {
            "brands": matched["brands"],
            "products": matched["products"],
            "ingredients": matched["ingredients"],
            "raw_texts": all_texts,
            "image_count": len(image_urls),
            "processed_at": datetime.now().isoformat(),
        }
        em["ocr_analysis"] = result
        return result

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph 节点入口。批量处理 OfficialUpdates 中的帖子。"""
        if not self.enabled:
            return {}

        ofu_data = state.get("OfficialUpdates")
        if not ofu_data or not ofu_data.get("updates"):
            return {}

        updates = ofu_data["updates"]
        entries_to_process = [
            u for u in updates
            if not (u.get("engagement_metrics") or {}).get("ocr_analysis")
            and self._extract_image_urls(u)
        ]

        if not entries_to_process:
            return {}

        logger.info(f"OCRAgent: processing {len(entries_to_process)} entries with media...")

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time

        start = time.time()
        processed = 0

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self.process_entry, entry): entry
                for entry in entries_to_process
            }
            try:
                for future in as_completed(futures, timeout=self.timeout_seconds):
                    try:
                        future.result()
                        processed += 1
                    except Exception as e:
                        entry = futures[future]
                        logger.warning(f"OCRAgent: failed for {entry.get('id', '?')}: {e}")
                        em = entry.setdefault("engagement_metrics", {})
                        em["ocr_analysis"] = {
                            "brands": [], "products": [], "ingredients": [],
                            "raw_texts": [], "image_count": 0, "error": str(e),
                            "processed_at": datetime.now().isoformat(),
                        }
            except Exception as e:
                logger.warning(f"OCRAgent: timeout or error during batch processing: {e}")

        elapsed = time.time() - start
        logger.info(f"OCRAgent: processed {processed}/{len(entries_to_process)} entries in {elapsed:.1f}s")

        return {"OfficialUpdates": ofu_data}


def create_ocr_agent(config: Dict[str, Any]):
    """工厂函数：返回 LangGraph 兼容的节点函数。"""
    agent = OCRAgent(config)

    def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        return agent.invoke(state)

    return agent_node
