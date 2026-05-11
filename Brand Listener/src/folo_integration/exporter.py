"""
FOLO RPA Export integration for OfficialUpdatesAgent.

This module provides interfaces to read data exported by FOLO software via RPA.
Supports JSON, CSV, and Follow (SQLite .db) export formats.
"""
import json
import csv
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import time

from ..data_models.official_updates import OfficialUpdate, Platform, UpdateType


logger = logging.getLogger(__name__)


class FOLOExportError(Exception):
    """Base exception for FOLO export errors."""
    pass


class FOLOExporter:
    """Base class for FOLO RPA export integration."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize exporter with configuration.

        Args:
            config: Configuration dictionary with export settings
        """
        self.config = config
        self.export_path = config.get("export_path", "./data/exports")
        self.polling_interval = config.get("polling_interval_minutes", 15)
        self.lookback_hours = config.get("lookback_hours", 24)

    def get_updates(self, source_urls: List[str], since: Optional[datetime] = None) -> List[OfficialUpdate]:
        """
        Get updates for the given source URLs since the specified time.

        Args:
            source_urls: List of brand account URLs to monitor
            since: Only return updates published after this time

        Returns:
            List of OfficialUpdate objects
        """
        raise NotImplementedError("Subclasses must implement get_updates")

    def monitor_updates(self, source_urls: List[str], callback) -> None:
        """
        Monitor for new updates and call callback when updates are detected.

        Args:
            source_urls: List of brand account URLs to monitor
            callback: Function to call with new updates (List[OfficialUpdate])
        """
        raise NotImplementedError("Subclasses must implement monitor_updates")

    def _filter_by_time(self, updates: List[Dict[str, Any]], since: datetime) -> List[Dict[str, Any]]:
        """Filter updates by publication time."""
        filtered = []
        for update in updates:
            published_str = update.get("published_at")
            if not published_str:
                continue

            try:
                # Try various datetime formats
                if isinstance(published_str, (int, float)):
                    # Unix timestamp
                    published_at = datetime.fromtimestamp(published_str)
                elif "T" in published_str:
                    # ISO format
                    published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                else:
                    # Try common formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d-%m-%Y %H:%M:%S"]:
                        try:
                            published_at = datetime.strptime(published_str, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        logger.warning(f"Could not parse date: {published_str}")
                        continue

                if published_at >= since:
                    filtered.append(update)
            except Exception as e:
                logger.warning(f"Error parsing date {published_str}: {e}")
                continue

        return filtered

    def _transform_to_official_update(self, raw_update: Dict[str, Any], source_url: str) -> OfficialUpdate:
        """
        Transform raw FOLO export data to OfficialUpdate model.

        This is a generic transformer that should be overridden based on actual FOLO export format.
        """
        # Extract platform from source URL or raw data
        platform = self._detect_platform(source_url, raw_update)

        # Map FOLO update type to our UpdateType enum
        update_type = self._map_update_type(raw_update.get("type", "post"))

        # Parse published date
        published_at = self._parse_published_date(raw_update)

        # Create OfficialUpdate
        return OfficialUpdate(
            id=str(raw_update.get("id", "")),
            source_url=source_url,
            platform=platform,
            update_type=update_type,
            title=raw_update.get("title"),
            content=raw_update.get("content", ""),
            url=raw_update.get("url"),
            media_urls=raw_update.get("media_urls", []),
            thumbnail_url=raw_update.get("thumbnail_url"),
            published_at=published_at,
            engagement_metrics=raw_update.get("engagement_metrics", {}),
            raw_data=raw_update  # Keep raw data for debugging
        )

    def _detect_platform(self, source_url: str, raw_data: Dict[str, Any]) -> Platform:
        """Detect platform from source URL or raw data."""
        url_lower = source_url.lower()

        if "weibo.com" in url_lower or "rsshub://weibo" in url_lower:
            return Platform.WEIBO
        elif "douyin.com" in url_lower or "iesdouyin.com" in url_lower or "rsshub://douyin" in url_lower:
            return Platform.DOUYIN
        elif "xiaohongshu.com" in url_lower or "rsshub://xiaohongshu" in url_lower:
            return Platform.XIAOHONGSHU
        elif "bilibili.com" in url_lower or "rsshub://bilibili" in url_lower:
            return Platform.BILIBILI
        elif "taobao.com" in url_lower:
            return Platform.TAOBAO
        elif "jd.com" in url_lower:
            return Platform.JD
        elif "pinduoduo.com" in url_lower:
            return Platform.PINDUODUO
        elif "wechat.com" in url_lower or "mp.weixin.qq.com" in url_lower:
            return Platform.WECHAT
        else:
            # Check raw data for platform hint
            platform_str = raw_data.get("platform", "").lower()
            if "weibo" in platform_str:
                return Platform.WEIBO
            elif "douyin" in platform_str or "tiktok" in platform_str:
                return Platform.DOUYIN
            elif "xiaohongshu" in platform_str or "redbook" in platform_str:
                return Platform.XIAOHONGSHU
            elif "bilibili" in platform_str or "b站" in platform_str:
                return Platform.BILIBILI
            elif "website" in platform_str or "官网" in platform_str:
                return Platform.WEBSITE
            else:
                return Platform.OTHER

    def _map_update_type(self, folo_type: str) -> UpdateType:
        """Map FOLO update type string to UpdateType enum (classification done later by ContentClassificationAgent)."""
        return UpdateType.BRAND_CONTENT

    def _parse_published_date(self, raw_update: Dict[str, Any]) -> datetime:
        """Parse published date from raw data."""
        published_str = raw_update.get("published_at")
        if not published_str:
            return datetime.now()

        try:
            if isinstance(published_str, (int, float)):
                # Unix timestamp
                return datetime.fromtimestamp(published_str)
            elif "T" in published_str:
                # ISO format
                return datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            else:
                # Try common formats
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d-%m-%Y %H:%M:%S"]:
                    try:
                        return datetime.strptime(published_str, fmt)
                    except ValueError:
                        continue
                # Fallback to current time
                return datetime.now()
        except Exception as e:
            logger.warning(f"Could not parse published date '{published_str}': {e}")
            return datetime.now()


class FileBasedFOLOExporter(FOLOExporter):
    """FOLO exporter that reads from files in a directory."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.file_pattern = config.get("file_pattern", "*.json")
        self.export_dir = Path(self.export_path)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def get_updates(self, source_urls: List[str], since: Optional[datetime] = None) -> List[OfficialUpdate]:
        """
        Read updates from export files.

        Assumes files contain updates grouped by source or timestamp.
        """
        if since is None:
            since = datetime.now() - timedelta(hours=self.lookback_hours)

        all_updates = []

        # Find export files — always include .db alongside the configured pattern
        export_files = list(self.export_dir.glob(self.file_pattern))
        db_files = list(self.export_dir.glob("*.db"))
        for f in db_files:
            if f not in export_files:
                export_files.append(f)
        if not export_files:
            logger.warning(f"No export files found in {self.export_dir}")
            return []

        # Process each file
        for file_path in export_files:
            try:
                file_updates = self._read_file(file_path, source_urls, since)
                all_updates.extend(file_updates)
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                continue

        return all_updates

    def _read_file(self, file_path: Path, source_urls: List[str], since: datetime) -> List[OfficialUpdate]:
        """Read and parse a single export file."""
        updates = []

        # Determine file format
        if file_path.suffix.lower() == ".json":
            data = self._read_json_file(file_path)
        elif file_path.suffix.lower() == ".csv":
            data = self._read_csv_file(file_path)
        elif file_path.suffix.lower() == ".db":
            return self._read_db_file(file_path, since)
        else:
            logger.warning(f"Unsupported file format: {file_path.suffix}")
            return []

        # Process data based on expected structure
        if isinstance(data, list):
            # List of updates
            for item in data:
                # Check if item belongs to requested sources
                source_url = item.get("source_url") or item.get("url")
                if source_url in source_urls:
                    filtered = self._filter_by_time([item], since)
                    if filtered:
                        update = self._transform_to_official_update(filtered[0], source_url)
                        updates.append(update)
        elif isinstance(data, dict):
            # Dict keyed by source URL
            for source_url, source_updates in data.items():
                if source_url in source_urls and isinstance(source_updates, list):
                    filtered = self._filter_by_time(source_updates, since)
                    for item in filtered:
                        update = self._transform_to_official_update(item, source_url)
                        updates.append(update)

        return updates

    def _read_json_file(self, file_path: Path) -> Union[List, Dict]:
        """Read JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _read_csv_file(self, file_path: Path) -> List[Dict]:
        """Read CSV file."""
        updates = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                updates.append(dict(row))
        return updates

    def _read_db_file(self, file_path: Path, since: datetime) -> List[OfficialUpdate]:
        """Read Follow (RSS reader) SQLite database and return OfficialUpdate list.

        Joins entries + feeds tables to get post content and brand account URL.
        published_at in Follow is stored as Unix milliseconds integer.
        """
        updates: List[OfficialUpdate] = []
        since_ms = int(since.timestamp() * 1000)

        try:
            conn = sqlite3.connect(str(file_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    e.id,
                    e.title,
                    e.url,
                    e.content,
                    e.description,
                    e.author,
                    e.author_url,
                    e.author_avatar,
                    e.published_at,
                    e.media,
                    f.site_url,
                    f.url  AS feed_url,
                    f.title AS feed_title,
                    f.image AS feed_image
                FROM entries e
                JOIN feeds f ON e.feed_id = f.id
                WHERE e.published_at >= ?
                ORDER BY e.published_at DESC
                """,
                (since_ms,),
            )
            rows = cur.fetchall()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"SQLite error reading {file_path}: {e}")
            return []

        for row in rows:
            try:
                source_url = row["site_url"] or row["feed_url"] or ""
                if not source_url:
                    continue

                published_at = datetime.fromtimestamp(row["published_at"] / 1000)

                # Parse media JSON → list of image URLs
                media_urls: List[str] = []
                if row["media"]:
                    try:
                        media_data = json.loads(row["media"])
                        if isinstance(media_data, list):
                            for item in media_data:
                                if isinstance(item, dict):
                                    url = item.get("url") or item.get("src") or item.get("href")
                                    if url:
                                        media_urls.append(url)
                                elif isinstance(item, str):
                                    media_urls.append(item)
                    except (json.JSONDecodeError, TypeError):
                        pass

                content = row["content"] or row["description"] or ""
                platform = self._detect_platform(source_url, {})

                update = OfficialUpdate(
                    id=str(row["id"]),
                    source_url=source_url,
                    platform=platform,
                    update_type=UpdateType.BRAND_CONTENT,
                    title=row["title"] or None,
                    content=content,
                    url=row["url"] or None,
                    media_urls=media_urls,
                    thumbnail_url=row["feed_image"] or None,
                    published_at=published_at,
                    engagement_metrics={
                        "author": row["author"] or "",
                        "author_url": row["author_url"] or "",
                        "author_avatar": row["author_avatar"] or "",
                        "feed_title": row["feed_title"] or "",
                    },
                    raw_data=dict(row),
                )
                updates.append(update)
            except Exception as e:
                logger.warning(f"Skipping entry {row['id']}: {e}")
                continue

        logger.info(f"Read {len(updates)} weibo entries from Follow DB: {file_path.name}")
        return updates

    def monitor_updates(self, source_urls: List[str], callback) -> None:
        """Monitor export directory for new files."""
        try:
            from watchfiles import watch
        except ImportError:
            logger.error("watchfiles not installed. Install with 'pip install watchfiles'")
            return

        logger.info(f"Monitoring {self.export_dir} for new exports...")

        for changes in watch(self.export_dir):
            for change_type, file_path in changes:
                if change_type == "added" and Path(file_path).suffix.lower() in [".json", ".csv", ".db"]:
                    logger.info(f"New export file detected: {file_path}")
                    try:
                        updates = self.get_updates(source_urls)
                        if updates:
                            callback(updates)
                    except Exception as e:
                        logger.error(f"Error processing new file {file_path}: {e}")


class MockFOLOExporter(FOLOExporter):
    """Mock exporter for testing without actual FOLO data."""

    def get_updates(self, source_urls: List[str], since: Optional[datetime] = None) -> List[OfficialUpdate]:
        """Generate mock updates for testing."""
        import random

        if since is None:
            since = datetime.now() - timedelta(hours=self.lookback_hours)

        updates = []
        platforms = list(Platform)
        update_types = list(UpdateType)

        for source_url in source_urls:
            # Generate 1-3 mock updates per source
            for i in range(random.randint(1, 3)):
                published_at = datetime.now() - timedelta(hours=random.randint(0, 23))
                if published_at < since:
                    continue

                update = OfficialUpdate(
                    id=f"mock_{source_url.replace('/', '_')}_{i}_{int(time.time())}",
                    source_url=source_url,
                    platform=random.choice(platforms),
                    update_type=random.choice(update_types),
                    title=f"Mock Update {i+1} from {source_url}",
                    content=f"This is a mock update content for testing. Published at {published_at.isoformat()}",
                    url=f"https://example.com/update/{i}",
                    media_urls=["https://example.com/image.jpg"] if random.random() > 0.5 else [],
                    published_at=published_at,
                    engagement_metrics={
                        "likes": random.randint(0, 1000),
                        "shares": random.randint(0, 500),
                        "comments": random.randint(0, 200)
                    }
                )
                updates.append(update)

        return updates

    def monitor_updates(self, source_urls: List[str], callback) -> None:
        """Mock monitoring - generates updates periodically."""
        import threading

        def _generate_updates():
            while True:
                time.sleep(self.polling_interval * 60)  # Convert minutes to seconds
                updates = self.get_updates(source_urls)
                if updates:
                    callback(updates)

        thread = threading.Thread(target=_generate_updates, daemon=True)
        thread.start()


def create_folo_exporter(config: Dict[str, Any]) -> FOLOExporter:
    """Factory function to create appropriate FOLO exporter based on config."""
    exporter_type = config.get("exporter_type", "file")

    if exporter_type == "file":
        return FileBasedFOLOExporter(config)
    elif exporter_type == "mock":
        return MockFOLOExporter(config)
    else:
        raise ValueError(f"Unknown exporter type: {exporter_type}")