"""
Data models for Analyst group agents output.
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


# ── OtherBrandCampaignAnalystAgent models ──

class CampaignComparison(BaseModel):
    model_config = ConfigDict(extra="ignore")

    competitor_name: str = Field(..., description="Competitor brand name")
    campaign_name: str = Field(..., description="Campaign name")
    campaign_type: str = Field(..., description="Campaign type (launch, promo, event, etc.)")
    platforms: List[str] = Field(default_factory=list, description="Platforms used")
    estimated_reach: int = Field(default=0, description="Estimated audience reach")
    engagement_rate: float = Field(default=0.0, description="Engagement rate (0-1)")
    sentiment_score: float = Field(default=0.0, description="Average sentiment score")
    start_date: Optional[datetime] = Field(None, description="Campaign start date")
    end_date: Optional[datetime] = Field(None, description="Campaign end date")
    key_messages: List[str] = Field(default_factory=list, description="Key campaign messages")
    effectiveness_score: float = Field(default=0.0, description="Overall effectiveness (0-1)")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class CompetitorCampaignAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    competitors: List[str] = Field(default_factory=list, description="Competitors analyzed")
    campaigns: List[CampaignComparison] = Field(default_factory=list, description="Campaign comparisons")
    total_campaigns_analyzed: int = Field(0, description="Total number of campaigns analyzed")
    market_insights: List[str] = Field(default_factory=list, description="Key market insights")
    recommendation: str = Field(default="", description="Strategic recommendation")
    analyzed_at: datetime = Field(default_factory=datetime.now, description="When analysis was performed")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "competitors": self.competitors,
            "campaigns": [c.to_dict() for c in self.campaigns],
            "total_campaigns_analyzed": self.total_campaigns_analyzed,
            "market_insights": self.market_insights,
            "recommendation": self.recommendation,
            "analyzed_at": self.analyzed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompetitorCampaignAnalysis":
        return cls(
            competitors=data.get("competitors", []),
            campaigns=[CampaignComparison(**c) for c in data.get("campaigns", [])],
            total_campaigns_analyzed=data.get("total_campaigns_analyzed", 0),
            market_insights=data.get("market_insights", []),
            recommendation=data.get("recommendation", ""),
            analyzed_at=datetime.fromisoformat(data["analyzed_at"]) if "analyzed_at" in data else datetime.now(),
        )


# ── UserFeedbackAnalystAgent models ──

class FeedbackTrend(BaseModel):
    model_config = ConfigDict(extra="ignore")

    trend_name: str = Field(..., description="Trend identifier")
    description: str = Field(..., description="Trend description")
    sentiment: Sentiment = Field(default=Sentiment.NEUTRAL, description="Prevailing sentiment")
    frequency: int = Field(default=0, description="Mention frequency")
    platforms: List[str] = Field(default_factory=list, description="Platforms where trend appears")
    sample_feedback: List[str] = Field(default_factory=list, description="Sample feedback excerpts")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class PainPoint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    issue: str = Field(..., description="The pain point / issue description")
    severity: int = Field(default=1, ge=1, le=10, description="Severity rating (1-10)")
    frequency: int = Field(default=0, description="How often this is mentioned")
    affected_aspect: str = Field(default="", description="Product/service aspect affected")
    suggested_improvement: str = Field(default="", description="Suggested improvement")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class UserFeedbackInsights(BaseModel):
    model_config = ConfigDict(extra="ignore")

    trends: List[FeedbackTrend] = Field(default_factory=list, description="Identified feedback trends")
    pain_points: List[PainPoint] = Field(default_factory=list, description="Key pain points")
    overall_sentiment: Sentiment = Field(default=Sentiment.NEUTRAL, description="Overall sentiment")
    summary: str = Field(default="", description="Executive summary of insights")
    analyzed_at: datetime = Field(default_factory=datetime.now, description="When analysis was performed")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trends": [t.to_dict() for t in self.trends],
            "pain_points": [p.to_dict() for p in self.pain_points],
            "overall_sentiment": self.overall_sentiment.value,
            "summary": self.summary,
            "analyzed_at": self.analyzed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserFeedbackInsights":
        return cls(
            trends=[FeedbackTrend(**t) for t in data.get("trends", [])],
            pain_points=[PainPoint(**p) for p in data.get("pain_points", [])],
            overall_sentiment=Sentiment(data.get("overall_sentiment", "neutral")),
            summary=data.get("summary", ""),
            analyzed_at=datetime.fromisoformat(data["analyzed_at"]) if "analyzed_at" in data else datetime.now(),
        )
