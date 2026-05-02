"""
Data models for ShoppingPlatformFeedbackAgent output.
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


class ShoppingPlatform(str, Enum):
    TAOBAO = "taobao"
    JD = "jd"
    PINDUODUO = "pinduoduo"
    OTHER = "other"


class ShoppingFeedbackItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique feedback identifier")
    platform: ShoppingPlatform = Field(..., description="Source shopping platform")
    product_id: str = Field(..., description="Product identifier")
    product_name: str = Field(..., description="Product name")
    rating: float = Field(default=5.0, ge=1.0, le=5.0, description="User rating (1-5)")
    review_content: str = Field(..., description="Review text content")
    sentiment: Sentiment = Field(default=Sentiment.NEUTRAL, description="Review sentiment")
    is_purchased: bool = Field(default=True, description="Whether the user purchased the product")
    likes_count: int = Field(default=0, description="Number of likes on this review")
    author_name: Optional[str] = Field(None, description="Review author")
    timestamp: datetime = Field(..., description="When the review was posted")
    detected_at: datetime = Field(default_factory=datetime.now, description="When detected")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ShoppingFeedback(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: List[ShoppingFeedbackItem] = Field(default_factory=list, description="List of shopping feedback items")
    timestamp: datetime = Field(default_factory=datetime.now, description="When data was collected")
    platform_count: int = Field(0, description="Number of platforms monitored")
    successful_platforms: List[str] = Field(default_factory=list, description="Successfully processed platforms")
    failed_platforms: Dict[str, str] = Field(default_factory=dict, description="Failed platforms and errors")

    def add_item(self, item: ShoppingFeedbackItem) -> None:
        self.items.append(item)

    def add_successful_platform(self, platform: str) -> None:
        if platform not in self.successful_platforms:
            self.successful_platforms.append(platform)
        self.platform_count = len(self.successful_platforms) + len(self.failed_platforms)

    def add_failed_platform(self, platform: str, error: str) -> None:
        self.failed_platforms[platform] = error
        self.platform_count = len(self.successful_platforms) + len(self.failed_platforms)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "timestamp": self.timestamp.isoformat(),
            "platform_count": self.platform_count,
            "successful_platforms": self.successful_platforms,
            "failed_platforms": self.failed_platforms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShoppingFeedback":
        items = [ShoppingFeedbackItem(**item) for item in data.get("items", [])]
        return cls(
            items=items,
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            platform_count=data.get("platform_count", 0),
            successful_platforms=data.get("successful_platforms", []),
            failed_platforms=data.get("failed_platforms", {}),
        )
