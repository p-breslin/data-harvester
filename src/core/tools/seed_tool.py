import asyncio
import json
import logging
from dataclasses import dataclass
from typing import List
from urllib.parse import urlparse

from agno.tools import tool
from crawl4ai import AsyncLogger, AsyncUrlSeeder, SeedingConfig
from pydantic import ValidationError

from core.models import SeededUrl
from core.utils.logger import log_tools

log = logging.getLogger(__name__)
tool_name = "seed_tool"
tool_log = log_tools(tool_name)


@dataclass
class SeedConfig:
    """Configuration for domain-aware URL seeding. Holds the tunable parameters for a seeding operation."""

    domain: str  # target domain to search within
    query: str  # search query for scoring relevance
    top_k: int = 5  # max number of top-scoring URLs to return
    score_threshold: float = 0.3  # min relevance score a URL must have
    max_urls: int = 500  # max number of URLs to initially discover before ranking
    scoring_method: str = "bm25"  # relevance scoring algo ('bm25' is fast + effective)
    source: str = "sitemap+cc"  # where to find URLs (+'cc' for Common Crawl)
    timeout_seconds: float = 360.0  # max time to wait for completion
    verbose: bool = False  # control AsyncLogger verbosity


def normalize_domain(domain: str) -> str:
    """Ensures only the netloc is extracted (adds a scheme if missing)."""
    if "://" not in domain:
        domain = "https://" + domain
    parsed = urlparse(domain)
    return parsed.netloc


async def discover_urls(config: SeedConfig) -> List[SeededUrl]:
    """Discovers and ranks URLs from a specific domain based on a query."""
    domain = normalize_domain(config.domain)
    tool_log.info(
        f"[{tool_name}] Seeding domain '{domain}' for query: '{config.query}'"
    )

    # Instantiate the config object required by Crawl4AI's AsyncUrlSeeder
    seeding_cfg = SeedingConfig(
        source=config.source,
        extract_head=True,
        query=config.query,
        scoring_method=config.scoring_method,
        score_threshold=config.score_threshold,
        max_urls=config.max_urls,
    )  # This maps the params from SeedConfig to the library's expected format

    try:
        async with AsyncUrlSeeder(logger=AsyncLogger(verbose=config.verbose)) as seeder:
            raw_results = await asyncio.wait_for(
                seeder.urls(domain, seeding_cfg), timeout=config.timeout_seconds
            )
    except asyncio.TimeoutError:
        log.error(f"[{tool_name}] URL seeding timed out")
        return []
    except Exception:
        log.exception(f"[{tool_name}] Unexpected error during seeding")
        return []

    # Filter out low-scoring entries
    filtered = [
        r
        for r in raw_results
        if r.get("relevance_score", 0.0) >= config.score_threshold
    ]
    # Sort by relevance_score descending
    filtered.sort(key=lambda x: x["relevance_score"], reverse=True)
    top_entries = filtered[: config.top_k]
    tool_log.debug(top_entries)

    results: List[SeededUrl] = []
    for entry in top_entries:
        try:
            results.append(
                SeededUrl(
                    url=entry["url"],
                    title=entry.get("head_data", {}).get("title", "No Title"),
                    relevance_score=entry.get("relevance_score", 0.0),
                    snippet=entry.get("head_data", {}).get("meta_description"),
                )
            )
        except ValidationError as ve:
            log.warning(
                f"[{tool_name}] Skipping invalid entry {entry.get('url')}: {ve}"
            )

    log.info(f"[{tool_name}] Returning {len(results)} URLs")
    return results


@tool(
    name="seed_tool",
    description="Discover and rank relevant URLs on a given domain for a query using Crawl4AI's AsyncUrlSeeder",
    show_result=True,
)
async def seed_tool(domain: str, query: str) -> str:
    """Agno tool wrapper for the `discover_urls` function.

    Args:
        domain (str): The target company domain.
        query (str): A specific search query to find relevant pages.

    Returns:
        A JSON string with a "results" array of {url, title, relevance_score, snippet}.
    """
    cfg = SeedConfig(domain=domain, query=query)
    seeded = await discover_urls(cfg)
    payload = [item.model_dump() for item in seeded]
    return json.dumps({"results": payload}, indent=2)
