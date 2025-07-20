from typing import Optional

from pydantic import Field, HttpUrl

from core.models.metadata import Metadata


class Supplier(Metadata):
    """Represents a company that supplies goods or services to the target company.

    This schema captures verifiable supplier relationships extracted from public sources.
    """

    name: str = Field(..., description="The name of the supplying organization.")
    description: Optional[str] = Field(
        None,
        description="Brief summary of the supplier's business or relevance to the target company.",
    )
    supplied_item_or_service: Optional[str] = Field(
        None, description="The specific item, material, component, or service supplied."
    )
    supply_type: Optional[str] = Field(
        None,
        description="Category of the supply relationship (e.g., manufacturing, logistics, software, staffing).",
    )
    website: Optional[HttpUrl] = Field(
        None, description="URL to the supplier's homepage or public profile."
    )

    class Config:
        model_config = {
            "extra": "forbid",
            "json_schema_extra": {
                "examples": [
                    {
                        "name": "TSMC",
                        "description": "Taiwan Semiconductor Manufacturing Company is a leading chip fabricator and key supplier for Apple's custom silicon.",
                        "supplied_item_or_service": "A-series and M-series system-on-chips (SoCs)",
                        "supply_type": "semiconductor fabrication",
                        "website": "https://www.tsmc.com/",
                        "source_url": "https://www.macrumors.com/guide/tsmc/",
                        "source_name": "MacRumors",
                        "scraped_at": "2025-07-19T18:00:00Z",
                    }
                ]
            },
        }
