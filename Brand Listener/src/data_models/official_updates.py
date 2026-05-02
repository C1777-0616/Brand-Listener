"""
Data models for OfficialUpdates output from OfficialUpdatesAgent.
Aligns with contract defined in interfaces/agent_contracts.json.
"""
from enum import Enum
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class Platform(str, Enum):
    """Platforms where brand updates can originate."""
    WEIBO = "weibo"
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    BILIBILI = "bilibili"
    WEBSITE = "website"
    WECHAT = "wechat"
    TAOBAO = "taobao"
    JD = "jd"
    PINDUODUO = "pinduoduo"
    OTHER = "other"


class UpdateType(str, Enum):
    """Business-oriented content type for brand official account posts."""
    NEW_PRODUCT = "new_product"       # 新品发布
    PROMOTION = "promotion"           # 促销活动
    KOL_COLLAB = "kol_collab"         # 代言合作
    USER_ENGAGEMENT = "user_engagement"  # 用户互动
    PRODUCT_CONTENT = "product_content"  # 产品种草
    OFFLINE_EVENT = "offline_event"   # 线下活动
    CORPORATE_NEWS = "corporate_news" # 企业资讯
    BRAND_CONTENT = "brand_content"   # 品牌内容（兜底）


class OfficialUpdate(BaseModel):
    """Individual official update from a brand account."""
    model_config = ConfigDict(extra="ignore")  # Ignore extra fields from source data

    # Core identifiers
    id: str = Field(..., description="Unique identifier for the update (from source)")
    source_url: str = Field(..., description="URL of the brand account/source")
    platform: Platform = Field(..., description="Platform where update was posted")

    # Content
    update_type: UpdateType = Field(default=UpdateType.BRAND_CONTENT, description="Type of update")
    title: Optional[str] = Field(None, description="Update title/headline")
    content: str = Field(..., description="Update content/text")
    url: Optional[str] = Field(None, description="URL to the specific update")

    # Media
    media_urls: List[str] = Field(default_factory=list, description="Media attachments (images, videos)")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail/preview image")

    # Metadata
    published_at: datetime = Field(..., description="When the update was published by the brand")
    detected_at: datetime = Field(default_factory=datetime.now, description="When detected by our system")

    # Engagement metrics (if available)
    engagement_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Platform engagement metrics (likes, shares, comments, views, etc.)"
    )

    # Source tracking
    raw_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Raw data from FOLO/RPA export for debugging"
    )

    def get_platform_display_name(self) -> str:
        """Get human-readable platform name."""
        platform_names = {
            Platform.WEIBO: "微博",
            Platform.DOUYIN: "抖音",
            Platform.XIAOHONGSHU: "小红书",
            Platform.BILIBILI: "B站",
            Platform.WECHAT: "微信",
            Platform.TAOBAO: "淘宝",
            Platform.JD: "京东",
            Platform.PINDUODUO: "拼多多",
            Platform.WEBSITE: "官网",
            Platform.OTHER: "其他"
        }
        return platform_names.get(self.platform, self.platform.value)


class OfficialUpdates(BaseModel):
    """Collection of official updates from multiple sources."""
    updates: List[OfficialUpdate] = Field(default_factory=list, description="List of official updates")
    timestamp: datetime = Field(default_factory=datetime.now, description="When data was collected")
    source_count: int = Field(0, description="Number of sources monitored")
    successful_sources: List[str] = Field(default_factory=list, description="URLs of successfully processed sources")
    failed_sources: Dict[str, str] = Field(default_factory=dict, description="Failed sources and error messages")

    def add_update(self, update: OfficialUpdate) -> None:
        """Add an update to the collection."""
        self.updates.append(update)

    def add_successful_source(self, source_url: str) -> None:
        """Mark a source as successfully processed."""
        if source_url not in self.successful_sources:
            self.successful_sources.append(source_url)
        self.source_count = len(self.successful_sources) + len(self.failed_sources)

    def add_failed_source(self, source_url: str, error: str) -> None:
        """Mark a source as failed with error message."""
        self.failed_sources[source_url] = error
        self.source_count = len(self.successful_sources) + len(self.failed_sources)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LangGraph state."""
        return {
            "updates": [update.model_dump() for update in self.updates],
            "timestamp": self.timestamp.isoformat(),
            "source_count": self.source_count,
            "successful_sources": self.successful_sources,
            "failed_sources": self.failed_sources
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OfficialUpdates":
        """Create from dictionary (e.g., from LangGraph state)."""
        updates = [OfficialUpdate(**update) for update in data.get("updates", [])]
        return cls(
            updates=updates,
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            source_count=data.get("source_count", 0),
            successful_sources=data.get("successful_sources", []),
            failed_sources=data.get("failed_sources", {})
        )