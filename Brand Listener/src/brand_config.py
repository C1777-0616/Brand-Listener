"""
Brand configuration management for FOLO Weibo monitoring.

Provides CRUD operations for brand configurations persisted to data/brands.json.
Each brand config defines which Weibo accounts to monitor via FOLO RPA.
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_PATH = DATA_DIR / "brands.json"


class BrandConfig(BaseModel):
    """Configuration for a monitored brand."""
    id: str = Field(..., description="Unique brand identifier")
    name: str = Field(..., description="Brand display name")
    weibo_uid: str = Field(..., description="Weibo UID or domain (e.g. '1234567890')")
    weibo_url: str = Field(..., description="Full Weibo profile URL")
    platforms: List[str] = Field(default_factory=lambda: ["weibo"], description="Monitored platforms")
    enabled: bool = Field(default=True, description="Whether monitoring is active")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class BrandConfigManager:
    """Manages brand configurations persisted to a JSON file."""

    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self._ensure_dir()

    def _ensure_dir(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _read(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write(self, data: List[Dict[str, Any]]):
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def list_brands(self) -> List[BrandConfig]:
        return [BrandConfig(**item) for item in self._read()]

    def get_brand(self, brand_id: str) -> Optional[BrandConfig]:
        for item in self._read():
            if item["id"] == brand_id:
                return BrandConfig(**item)
        return None

    def add_brand(self, config: BrandConfig) -> BrandConfig:
        data = self._read()
        # Check duplicate id
        if any(item["id"] == config.id for item in data):
            raise ValueError(f"Brand with id '{config.id}' already exists")
        config.created_at = datetime.now().isoformat()
        config.updated_at = config.created_at
        data.append(config.model_dump())
        self._write(data)
        logger.info(f"Added brand: {config.name} (id={config.id}, weibo={config.weibo_uid})")
        return config

    def update_brand(self, brand_id: str, updates: Dict[str, Any]) -> Optional[BrandConfig]:
        data = self._read()
        for item in data:
            if item["id"] == brand_id:
                item.update(updates)
                item["updated_at"] = datetime.now().isoformat()
                self._write(data)
                logger.info(f"Updated brand: {brand_id}")
                return BrandConfig(**item)
        return None

    def delete_brand(self, brand_id: str) -> bool:
        data = self._read()
        new_data = [item for item in data if item["id"] != brand_id]
        if len(new_data) == len(data):
            return False
        self._write(new_data)
        logger.info(f"Deleted brand: {brand_id}")
        return True

    def get_enabled_weibo_sources(self) -> List[str]:
        """Return weibo_url list of all enabled brands (for pipeline input)."""
        return [
            b.weibo_url for b in self.list_brands()
            if b.enabled and "weibo" in b.platforms
        ]


# Singleton for app-wide use
_manager: Optional[BrandConfigManager] = None


def get_brand_config_manager() -> BrandConfigManager:
    global _manager
    if _manager is None:
        _manager = BrandConfigManager()
    return _manager


if __name__ == "__main__":
    # Quick test
    mgr = get_brand_config_manager()
    print("=== Brand Config Manager Test ===")
    print(f"Config path: {CONFIG_PATH}")

    # Add test brands
    try:
        mgr.add_brand(BrandConfig(
            id="our_brand",
            name="我方品牌 (BrandListen)",
            weibo_uid="brandlisten_official",
            weibo_url="https://weibo.com/brandlisten_official",
        ))
    except ValueError as e:
        print(f"  (skipped: {e})")

    try:
        mgr.add_brand(BrandConfig(
            id="competitor_a",
            name="竞品A (高端旗舰线)",
            weibo_uid="competitor_a_official",
            weibo_url="https://weibo.com/competitor_a_official",
        ))
    except ValueError as e:
        print(f"  (skipped: {e})")

    brands = mgr.list_brands()
    print(f"\nTotal brands: {len(brands)}")
    for b in brands:
        print(f"  - {b.name} | weibo={b.weibo_uid} | enabled={b.enabled}")

    sources = mgr.get_enabled_weibo_sources()
    print(f"\nEnabled Weibo sources: {sources}")
    print("\nDone.")
