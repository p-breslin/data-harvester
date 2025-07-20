from enum import Enum
from typing import Optional

from pydantic import Field, HttpUrl

from core.models.metadata import Metadata


class OfferingType(str, Enum):
    PRODUCT = "product"
    SERVICE = "service"
    BOTH = "both"


class Competitor(Metadata):
    """Represents a company or product identified as a competitor to the target company.

    This schema is intended for structured extraction of known or likely competitors based on market context.
    """

    name: str = Field(..., description="The name of the competing company or product.")
    offering: Optional[str] = Field(
        None,
        description="Primary product, service, or offering that competes with the target company.",
    )
    description: Optional[str] = Field(
        None, description="A brief explanation of the competitor and what they offer."
    )
    product_or_service: Optional[str] = Field(
        None,
        description="Key product or service offered by the competitor that overlaps with the target company's offerings.",
    )
    market_overlap: Optional[str] = Field(
        None,
        description="Short summary of how this competitor overlaps with the target company (e.g., same vertical, same customer base, same core functionality).",
    )
    website: Optional[HttpUrl] = Field(
        None, description="URL to the competitor's homepage or main product page."
    )

    class Config:
        model_config = {
            "extra": "forbid",
            "json_schema_extra": {
                "examples": [
                    {
                        "name": "Samsung Electronics",
                        "offering": "both",
                        "description": "A global electronics manufacturer and Apple's primary competitor in smartphones and consumer devices.",
                        "product_or_service": "Galaxy smartphone series",
                        "market_overlap": "Smartphones, tablets, and wearable devices targeting the same consumer base.",
                        "website": "https://www.samsung.com/",
                        "source_url": "https://www.businessinsider.com/apple-vs-samsung-smartphone-market-share-2023-3",
                        "source_name": "Business Insider",
                        "scraped_at": "2025-07-19T17:30:00Z",
                    }
                ]
            },
        }
