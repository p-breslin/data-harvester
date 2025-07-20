from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class Metadata(BaseModel):
    """Common metadata fields for all scraped entities."""

    source_url: Optional[HttpUrl] = Field(
        None, description="URL where the data was extracted from."
    )
    source_name: Optional[str] = Field(
        None, description="Name of the source (e.g., 'TechCrunch', 'Company Site')."
    )
    scraped_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the data was extracted.",
    )
