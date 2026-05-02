"""
Data models for SocialMediaFeedbackAgent output.
Aligns with contract defined in interfaces/agent_contracts.json.
"""
from enum import Enum
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class FeedbackPlatform(str, Enum):
    WEIBO = "weibo"
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    BILIBILI = "bilibili"
    WECHAT = "wechat"
    OTHER = "other"


class SocialFeedbackItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique feedback identifier")
    platform: FeedbackPlatform = Field(..., description="Source platform")
    source_url: str = Field(..., description="Source URL")
    content: str = Field(..., description="Feedback content/text")
    sentiment: Sentiment = Field(default=Sentiment.NEUTRAL, description="Content sentiment")
    likes: int = Field(default=0, description="Number of likes")
    comments: int = Field(default=0, description="Number of comments")
    shares: int = Field(default=0, description="Number of shares")
    author_name: Optional[str] = Field(None, description="Author display name")
    is_influencer: bool = Field(default=False, description="Whether author is an influencer")
    timestamp: datetime = Field(..., description="When the feedback was posted")
    detected_at: datetime = Field(default_factory=datetime.now, description="When detected")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class SocialMediaFeedback(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: List[SocialFeedbackItem] = Field(default_factory=list, description="List of feedback items")
    timestamp: datetime = Field(default_factory=datetime.now, description="When data was collected")
    source_count: int = Field(0, description="Number of sources monitored")
    successful_sources: List[str] = Field(default_factory=list, description="Successfully processed sources")
    failed_sources: Dict[str, str] = Field(default_factory=dict, description="Failed sources and errors")

    def add_item(self, item: SocialFeedbackItem) -> None:
        self.items.append(item)

    def add_successful_source(self, source_url: str) -> None:
        if source_url not in self.successful_sources:
            self.successful_sources.append(source_url)
        self.source_count = len(self.successful_sources) + len(self.failed_sources)

    def add_failed_source(self, source_url: str, error: str) -> None:
        self.failed_sources[source_url] = error
        self.source_count = len(self.successful_sources) + len(self.failed_sources)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "timestamp": self.timestamp.isoformat(),
            "source_count": self.source_count,
            "successful_sources": self.successful_sources,
            "failed_sources": self.failed_sources,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SocialMediaFeedback":
        items = [SocialFeedbackItem(**item) for item in data.get("items", [])]
        return cls(
            items=items,
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            source_count=data.get("source_count", 0),
            successful_sources=data.get("successful_sources", []),
            failed_sources=data.get("failed_sources", {}),
        )
