import json
import logging
from typing import Any, Dict, List

from agno.tools import tool
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    LLMConfig,
)
from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from core.utils.helpers import load_yaml, resolve_api_key

log = logging.getLogger(__name__)


@tool(
    name="extract_tool",
    description=(
        "Extracts structured data from a list of URLs based on a Pydantic schema. "
        "Runs URLs in parallel via a persistent browser and returns per-URL status + data."
    ),
    show_result=True,
)
async def extract_tool(
    urls: List[str],
    schema_json: str,
) -> str:
    """Extracts structured data from a list of URLs using an LLM.

    Args:
        urls (list[str]): List of page URLs to extract.
        schema (Pydantic Model): JSON-string or Dict from `.model_json_schema()`.

    Returns:
        JSON string of results.
    """
    cfg = load_yaml("tools", key="extract_tool")
    try:
        schema_dict = json.loads(schema_json)
    except json.JSONDecodeError:
        return json.dumps(
            {"results": [], "error": "Invalid JSON for schema_json"}, indent=2
        )
    log.info(f"[ExtractTool] Starting extraction on {len(urls)} URLs.")

    # Configure the LLM extraction strategy
    api_token = resolve_api_key(cfg["provider"])
    llm_cfg = LLMConfig(provider=cfg["provider"], api_token=api_token)
    extraction_strategy = LLMExtractionStrategy(
        llm_config=llm_cfg,
        schema_json=schema_dict,
        extraction_type="schema",
        instruction=cfg["instructions"],
        apply_chunking=False,
    )

    # Create a PruningContentFilter for adaptive filtering to specific extraction task
    pruning_filter = PruningContentFilter(
        threshold=0.5,
        threshold_type="dynamic",  # Adaptive cutoff based on document
        min_word_threshold=None,
    )

    # Configure the CrawlerRunConfig
    excluded_tags = ["nav", "footer", "aside", "header", "script", "style"]
    crawl_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=extraction_strategy,
        exclude_external_links=True,
        excluded_tags=excluded_tags,
        markdown_generator=DefaultMarkdownGenerator(pruning_filter),
    )

    # Dispatcher: no rate-limit, configurable concurrency
    dispatcher = MemoryAdaptiveDispatcher(
        rate_limiter=None, max_session_permit=cfg["max_concurrent"]
    )

    try:
        async with AsyncWebCrawler(
            config=BrowserConfig(browser_mode="builtin", headless=True)
        ) as crawler:
            container = await crawler.arun_many(
                urls=urls, config=crawl_cfg, dispatcher=dispatcher
            )
    except Exception as e:
        log.exception("[ExtractTool] Failed to launch crawler")
        # global failure
        return json.dumps(
            {
                "results": [
                    {"url": u, "status": "failed", "error": str(e)} for u in urls
                ]
            },
            indent=2,
        )

    # Normalize container to iterable
    if isinstance(container, list):
        iterable = container  # already a list of results
    else:
        iterable = [res async for res in container]

    # Process each result
    output: List[Dict[str, Any]] = []
    for res in iterable:
        entry = {"url": getattr(res, "url", None)}
        if getattr(res, "success", False) and getattr(res, "extracted_content", None):
            raw = res.extracted_content
            try:
                data = json.loads(raw)
                entry.update(status="success", data=data)
            except json.JSONDecodeError:
                entry.update(
                    status="failed",
                    error="Invalid JSON from LLM",
                    raw_output=raw,
                )
        else:
            err = getattr(res, "error_message", "Extraction failed")
            entry.update(status="failed", error=err)
        output.append(entry)

    return json.dumps({"results": output}, indent=2, default=str)
