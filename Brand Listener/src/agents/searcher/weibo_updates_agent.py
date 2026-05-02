"""
WeiboUpdatesAgent - monitors official Weibo account updates via FOLO SQLite export.

Sub-agent under OfficialUpdatesAgent, responsible solely for Weibo platform data.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from ...data_models.official_updates import OfficialUpdates, OfficialUpdate
from ...folo_integration.exporter import create_folo_exporter, FOLOExportError


logger = logging.getLogger(__name__)


class WeiboUpdatesAgent:
    """Sub-agent that fetches Weibo updates via FOLO SQLite export."""

    def __init__(self, config: Dict[str, Any]):
        folo_config = config.get("folo_config", {})
        self.exporter = create_folo_exporter(folo_config)
        self.max_sources = config.get("max_sources", 50)
        self.lookback_hours = config.get("lookback_hours", 24)
        self.last_run_time = None
        self.processed_updates = set()

    def fetch(self, sources: List[str], since: datetime) -> List[OfficialUpdate]:
        """Fetch Weibo updates from FOLO exporter for given sources."""
        try:
            updates = self.exporter.get_updates(sources, since)
            unique = []
            for u in updates:
                uid = f"{u.source_url}:{u.id}"
                if uid not in self.processed_updates:
                    unique.append(u)
                    self.processed_updates.add(uid)
            return unique
        except FOLOExportError as e:
            logger.error(f"WeiboUpdatesAgent FOLO error: {e}")
            return []
        except Exception as e:
            logger.error(f"WeiboUpdatesAgent unexpected error: {e}", exc_info=True)
            return []

    def since_time(self) -> datetime:
        """Calculate lookback start time."""
        if self.last_run_time:
            since = self.last_run_time
        else:
            since = datetime.now() - timedelta(hours=self.lookback_hours)
        max_lookback = datetime.now() - timedelta(hours=self.lookback_hours)
        return max(since, max_lookback)
