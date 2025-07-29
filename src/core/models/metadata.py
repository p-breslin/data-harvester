from typing import Optional

from pydantic import BaseModel, Field


class Metadata(BaseModel):
    """Common metadata fields for all scraped entities."""

    source_url: Optional[str] = Field(
        None, description="URL where the data was extracted from."
    )
    source_name: Optional[str] = Field(
        None, description="Name of the source (e.g., 'TechCrunch', 'Apple')."
    )
    scraped_at: Optional[str] = Field(
        None,
        description="Timestamp when the data was extracted.",
    )
