from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class WebPage(BaseModel):
    """Represents a single search result page."""

    url: str = Field(..., description="The full URL of the webpage")
    title: str = Field(..., description="The title of the webpage")
    snippet: Optional[str] = Field(
        None,
        description="Optional preview text or snippet from the search result, if available.",
    )


class WebPageList(BaseModel):
    """Holds exactly five webpages returned by the web search agent."""

    results: List[WebPage] = Field(
        ...,
        min_items=5,
        max_items=5,
        description="A list of exactly five WebPage entries",
    )


class SeededUrl(BaseModel):
    """Defines the strict schema for the output of the tool (a seeded URL)."""

    url: str = Field(..., description="The full URL of the webpage")
    title: str = Field(..., description="The title of the webpage")
    relevance_score: float = Field(..., description="Relevance to the user query")


class SeededUrlList(BaseModel):
    results: List[SeededUrl]


class CrawledPage(BaseModel):
    """Represents a discovered page during the crawling process."""

    url: str = Field(..., description="The discovered URL from the crawling process")
    relevance_score: float = Field(
        ...,
        description="Score assigned to this URL indicating its estimated relevance to the target schema.",
    )
    parent_url: str = Field(
        ...,
        description="The URL from which this page was discovered (used to preserve crawl lineage).",
    )


class CrawledPageList(BaseModel):
    """List of discovered pages with associated scores."""

    pages: List[CrawledPage] = Field(
        default_factory=list,
        description="List of discovered pages with their associated relevance scores.",
    )
    source_domain: Optional[str] = Field(
        ...,
        description="The top-level domain these pages were discovered from (used for domain-level policies).",
    )
