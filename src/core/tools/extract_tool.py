import json
import logging
from datetime import datetime, timezone
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
from core.utils.logger import log_tools

# Setup
log = logging.getLogger(__name__)
tool_name = "extract_tool"
tool_log = log_tools(tool_name)


@tool(
    name=tool_name,
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
    cfg = load_yaml("tools", key=tool_name)
    try:
        schema_dict = json.loads(schema_json)
    except json.JSONDecodeError:
        return json.dumps(
            {"results": [], "error": "Invalid JSON for schema_json"}, indent=2
        )
    tool_log.info(f"[{tool_name}] Starting extraction on {urls}.")

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

    # Custom BrowserConfig for stealth
    browser_cfg = BrowserConfig(
        browser_type="chromium",
        headless=True,  # keeps browser window hidden
        viewport_width=1600,  # full desktop version
        viewport_height=900,
        user_agent=cfg.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/117.0.0.0 Safari/537.36",
        ),  # anti-bot logic
        ignore_https_errors=True,
        use_persistent_context=True,  # reuse the same browser context
        extra_args=["--disable-blink-features=AutomationControlled"],  # anti-bot logic
    )

    # Configure the CrawlerRunConfig
    excluded_tags = ["nav", "footer", "aside", "header", "script", "style"]
    crawl_cfg = CrawlerRunConfig(
        wait_until="networkidle",  # wait for network to quiet down
        page_timeout=20000,  # 20s nav timeout
        delay_before_return_html=0.5,  # small pause before grab
        scan_full_page=True,  # scroll to load lazy content
        simulate_user=True,  # wiggle mouse, etc.
        override_navigator=True,  # spoof navigator props
        magic=True,  # auto-handle popups/consent
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
            config=BrowserConfig(browser_mode=browser_cfg)
        ) as crawler:
            container = await crawler.arun_many(
                urls=urls, config=crawl_cfg, dispatcher=dispatcher
            )
    except Exception as e:
        log.exception(f"[{tool_name}] Failed to launch crawler")
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
        entry = {
            "url": getattr(res, "url", None),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        if getattr(res, "success", False) and getattr(res, "extracted_content", None):
            raw = res.extracted_content
            try:
                data = json.loads(raw)
                entry.update(status="success", data=data)
                tool_log.debug(entry)

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
