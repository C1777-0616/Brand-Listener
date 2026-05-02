"""
OfficialUpdatesAgent - orchestrator that collects official brand account updates
from multiple platform sub-agents and merges them into a single OfficialUpdates output.

Sub-agents (one per platform):
  - WeiboUpdatesAgent  — Weibo via FOLO SQLite export (current)
  # Future: XiaohongshuUpdatesAgent, DouyinUpdatesAgent, ...

LangGraph node name and output key are unchanged: "official_updates_agent" → OfficialUpdates.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime

from ...data_models.official_updates import OfficialUpdates, OfficialUpdate
from .weibo_updates_agent import WeiboUpdatesAgent
from .xiaohongshu_updates_agent import XiaohongshuUpdatesAgent


logger = logging.getLogger(__name__)


class OfficialUpdatesAgent:
    """Orchestrator: runs all platform sub-agents and merges results into OfficialUpdates."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_sources = config.get("max_sources", 50)

        # Instantiate sub-agents
        self.sub_agents: List[tuple[str, Any]] = [
            ("weibo", WeiboUpdatesAgent(config)),
            ("xiaohongshu", XiaohongshuUpdatesAgent(config)),
        ]

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            sources = self._extract_sources(state)
            if not sources:
                logger.warning("No sources provided to OfficialUpdatesAgent")
                return {"OfficialUpdates": OfficialUpdates().to_dict()}

            if len(sources) > self.max_sources:
                logger.warning(f"Limiting sources from {len(sources)} to {self.max_sources}")
                sources = sources[:self.max_sources]

            all_updates: List[OfficialUpdate] = []
            for platform, agent in self.sub_agents:
                since = agent.since_time()
                updates = agent.fetch(sources, since)
                agent.last_run_time = datetime.now()
                logger.info(f"OfficialUpdatesAgent[{platform}]: {len(updates)} updates")
                all_updates.extend(updates)

            result = OfficialUpdates(updates=all_updates)
            for source in sources:
                result.add_successful_source(source)

            logger.info(f"OfficialUpdatesAgent total: {len(all_updates)} updates from {len(sources)} sources")
            return {"OfficialUpdates": result.to_dict()}

        except Exception as e:
            logger.error(f"OfficialUpdatesAgent failed: {e}", exc_info=True)
            return {"OfficialUpdates": OfficialUpdates().to_dict()}

    def _extract_sources(self, state: Dict[str, Any]) -> List[str]:
        sources = state.get("sources", [])
        if isinstance(sources, str):
            sources = [sources]
        elif not isinstance(sources, list):
            logger.warning(f"Expected list of sources, got {type(sources)}")
            return []
        valid = []
        for s in sources:
            if isinstance(s, str) and s.startswith(("http://", "https://")):
                valid.append(s)
            else:
                logger.warning(f"Invalid source URL: {s}")
        return valid


def create_official_updates_agent(config: Dict[str, Any]):
    """Factory: returns a LangGraph-compatible node function."""
    agent = OfficialUpdatesAgent(config)

    def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        return agent.invoke(state)

    return agent_node