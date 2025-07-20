from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class WebPage(BaseModel):
    """Represents a single search result page."""

    url: str = Field(..., description="The full URL of the webpage")
    title: str = Field(..., description="The title of the webpage")


class WebPageCollection(BaseModel):
    """Holds exactly five webpages returned by the web search agent."""

    webpages: List[WebPage] = Field(
        ...,
        min_items=5,
        max_items=5,
        description="A list of exactly five WebPage entries",
    )


class CrawledURLs(BaseModel):
    url: str = Field(..., description="The discovered URL from the crawling process")
    score: float = Field(
        ...,
        description="Relevance score assigned by the URL scorer, used for prioritization in crawling strategies",
    )


class CrawledURLsList(BaseModel):
    urls: List[CrawledURLs] = Field(
        default_factory=list,
        description="List of discovered URLs with their associated scores",
    )
