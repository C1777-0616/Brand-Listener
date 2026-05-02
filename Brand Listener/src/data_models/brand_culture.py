"""
Data models for BrandCultureListeningAgent output.
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


class EventCategory(str, Enum):
    TRENDING_TOPIC = "trending_topic"
    USER_DISCUSSION = "user_discussion"
    BRAND_MENTION = "brand_mention"
    CULTURAL_TREND = "cultural_trend"
    PUBLIC_OPINION = "public_opinion"
    OTHER = "other"


class BrandCultureEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique event identifier")
    brand_id: str = Field(..., description="Brand identifier")
    platform: str = Field(..., description="Source platform")
    content: str = Field(..., description="Event content/text")
    sentiment: Sentiment = Field(default=Sentiment.NEUTRAL, description="Content sentiment")
    category: EventCategory = Field(default=EventCategory.OTHER, description="Event category")
    source_url: Optional[str] = Field(None, description="Source URL")
    mention_count: int = Field(default=0, description="Number of mentions")
    engagement_count: int = Field(default=0, description="Total engagement")
    keywords: List[str] = Field(default_factory=list, description="Related keywords")
    timestamp: datetime = Field(..., description="When the event occurred")
    detected_at: datetime = Field(default_factory=datetime.now, description="When detected")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class CultureSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    brand_id: str = Field(..., description="Brand identifier")
    period_start: datetime = Field(..., description="Summary period start")
    period_end: datetime = Field(..., description="Summary period end")
    total_events: int = Field(default=0, description="Total events in period")
    dominant_categories: Dict[str, int] = Field(default_factory=dict, description="Event category distribution")
    sentiment_distribution: Dict[str, int] = Field(default_factory=dict, description="Sentiment distribution")
    top_keywords: List[str] = Field(default_factory=list, description="Top keywords in period")
    summary_text: str = Field(default="", description="Natural language summary")
    events: List[BrandCultureEvent] = Field(default_factory=list, description="Raw events")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "brand_id": self.brand_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_events": self.total_events,
            "dominant_categories": self.dominant_categories,
            "sentiment_distribution": self.sentiment_distribution,
            "top_keywords": self.top_keywords,
            "summary_text": self.summary_text,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CultureSummary":
        return cls(
            brand_id=data["brand_id"],
            period_start=datetime.fromisoformat(data["period_start"]),
            period_end=datetime.fromisoformat(data["period_end"]),
            total_events=data.get("total_events", 0),
            dominant_categories=data.get("dominant_categories", {}),
            sentiment_distribution=data.get("sentiment_distribution", {}),
            top_keywords=data.get("top_keywords", []),
            summary_text=data.get("summary_text", ""),
            events=[BrandCultureEvent(**e) for e in data.get("events", [])],
        )
