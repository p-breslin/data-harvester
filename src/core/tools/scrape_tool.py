import json
import logging
import os
from typing import List

from agno.tools import tool
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    LLMConfig,
)
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from dotenv import load_dotenv

from core.models import ExtractionOutput
from core.utils.helpers import load_yaml

load_dotenv()
log = logging.getLogger(__name__)
MODEL_MAP = {"product": ExtractionOutput}


@tool(
    name="scrape_tool",
    description="Web scraping with Crawl4AI",
    show_result=True,
)
async def scrape_tool(urls: List[str], mode: str) -> List[dict]:
    """Scrapes structured data from a list of URLs using LLM extraction.

    Args:
        urls: The URLs to scrape from
        mode: The extraction mode ('product' or 'revenue')
    """
    log.info(f"Starting extraction from {len(urls)} URLs")
    cfg = load_yaml(file=f"{mode}_info")
    response_model = MODEL_MAP[mode]

    # Configure LLM extraction strategy
    extraction_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider="gemini/gemini-2.0-flash", api_token=os.getenv("GEMINI_API_KEY")
        ),
        schema=response_model.model_json_schema(),
        extraction_type="schema",
        instruction=cfg["extraction_instruction"],
        chunk_token_threshold=1000,
        apply_chunking=True,
        input_format="html",
        extra_args={"temperature": 0.1, "max_tokens": 800},
    )

    # target_elements=cfg["target_elements"],
    # excluded_tags=cfg["excluded_tags"],

    # Extraction configuration
    extraction_cfg = CrawlerRunConfig(
        extraction_strategy=extraction_strategy,
        cache_mode=CacheMode.BYPASS,
        verbose=True,
    )
    browser_cfg = BrowserConfig(headless=True, verbose=False)

    # Execute extraction
    async with AsyncWebCrawler(config=browser_cfg) as scraper:
        results = []
        try:
            # Extract from all URLs using arun_many
            extraction_results = await scraper.arun_many(
                urls=urls, config=extraction_cfg
            )

            # Now iterate asynchronously over each result
            for result in extraction_results:
                if not result.success:
                    log.warning(f"Failed to extract from {result.url}")
                    continue

                extraction_strategy.show_usage()
                results.append(json.loads(result.extracted_content))

        except Exception as e:
            log.exception("Error during extraction:", e)
            # Return an empty list on failure to maintain type consistency
            return []

    return results
