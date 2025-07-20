from typing import Optional

from pydantic import Field, HttpUrl

from core.models.metadata import Metadata


class Customer(Metadata):
    """Represents an organization or individual identified as a customer of the target company.

    This schema is designed to capture verifiable references to customers found in public sources.
    """

    name: str = Field(
        ..., description="The name of the customer (individual or organization)."
    )
    description: Optional[str] = Field(
        None,
        description="A brief summary of the customer, their industry, or relevance.",
    )
    industry: Optional[str] = Field(
        None,
        description="The industry or sector the customer operates in (e.g., healthcare, retail).",
    )
    relationship_summary: Optional[str] = Field(
        None,
        description="Short description of how the customer uses or has used the company's products/services.",
    )
    logo_url: Optional[HttpUrl] = Field(
        None, description="URL pointing to the customer's logo image, if available."
    )

    class Config:
        model_config = {
            "extra": "forbid",
            "json_schema_extra": {
                "examples": [
                    {
                        "name": "United Airlines",
                        "description": "A major U.S. airline with global passenger and cargo operations.",
                        "industry": "Aviation",
                        "relationship_summary": "Equipped pilots and ground crew with iPads to enhance operations and reduce paper-based processes.",
                        "logo_url": "https://united.com/assets/img/united-logo.svg",
                        "source_url": "https://www.apple.com/business/success-stories/united-airlines/",
                        "source_name": "Apple Business Success Stories",
                        "scraped_at": "2025-07-19T17:00:00Z",
                    }
                ]
            },
        }
