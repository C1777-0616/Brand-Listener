"""
Data models for TemplateDrivenReportAgent output.
Aligns with contract defined in interfaces/agent_contracts.json.
"""
from enum import Enum
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ReportFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    PDF = "pdf"  # placeholder for future PDF generation


class ReportTemplate(str, Enum):
    WEEKLY_DIGEST = "weekly_digest"
    CAMPAIGN_ANALYSIS = "campaign_analysis"
    COMPETITOR_REVIEW = "competitor_review"
    CUSTOM = "custom"


class ReportSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content (markdown)")
    data_ref: Optional[str] = Field(None, description="Reference to source data key")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Report(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique report identifier")
    title: str = Field(..., description="Report title")
    template: ReportTemplate = Field(default=ReportTemplate.CUSTOM, description="Report template used")
    sections: List[ReportSection] = Field(default_factory=list, description="Report sections")
    created_at: datetime = Field(default_factory=datetime.now, description="When the report was created")
    data_summary: Dict[str, Any] = Field(default_factory=dict, description="Summary of data used")

    def to_markdown(self) -> str:
        """Generate markdown output."""
        lines = [f"# {self.title}", f"*Generated: {self.created_at.isoformat()}*\n"]
        for section in self.sections:
            lines.append(f"## {section.title}\n")
            lines.append(section.content)
            lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "template": self.template.value,
            "sections": [s.to_dict() for s in self.sections],
            "created_at": self.created_at.isoformat(),
            "data_summary": self.data_summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Report":
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            template=ReportTemplate(data.get("template", "custom")),
            sections=[ReportSection(**s) for s in data.get("sections", [])],
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            data_summary=data.get("data_summary", {}),
        )


class ReportBundle(BaseModel):
    """Container for all report output formats."""
    model_config = ConfigDict(extra="ignore")

    report: Report
    markdown: str = Field(default="", description="Markdown formatted report")
    json_data: str = Field(default="", description="JSON formatted report")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report": self.report.to_dict(),
            "markdown": self.markdown,
            "json_data": self.json_data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportBundle":
        return cls(
            report=Report.from_dict(data["report"]),
            markdown=data.get("markdown", ""),
            json_data=data.get("json_data", ""),
        )
