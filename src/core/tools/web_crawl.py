import json
import logging
from typing import List
from urllib.parse import urlparse

from agno.tools import tool
from agno.utils.json_io import CustomJSONEncoder
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
)
from crawl4ai.deep_crawling import (
    BestFirstCrawlingStrategy,
    ContentTypeFilter,
    DomainFilter,
    FilterChain,
    KeywordRelevanceScorer,
    URLPatternFilter,
)
from dotenv import load_dotenv

from core.utils.helpers import load_yaml

load_dotenv()
log = logging.getLogger(__name__)

MAX_DEPTH = 5
MAX_PAGES = 2


async def crawl4ai_deep_crawl(start_url: str, mode: str) -> List[dict]:
    """Uses Crawl4AI to crawl a website starting from the given page.

    Args:
        start_url (str): The URL to start crawling from.

    Returns:
        List(dict): list of discovered URLs with metadata.
    """
    log.info(f"Starting deep crawl for: {start_url}")
    cfg = load_yaml(file=f"{mode}_info")

    # 1) Scoring configuration (to prioritize certain URLs)
    keyword_scorer = KeywordRelevanceScorer(
        keywords=cfg["keywords"],
        weight=1.0,
    )

    # 2) Set up filters to stay within relevant domains and content
    domain = urlparse(start_url).netloc
    filter_chain = FilterChain(
        [
            DomainFilter(allowed_domains=[domain]),
            ContentTypeFilter(allowed_types=["text/html"]),
            URLPatternFilter(patterns=cfg["url_patterns"]),
        ]
    )

    # 3) Crawl configuration
    deep_crawl_cfg = CrawlerRunConfig(
        deep_crawl_strategy=BestFirstCrawlingStrategy(
            max_depth=MAX_DEPTH,
            max_pages=MAX_PAGES,
            include_external=False,  # Stay within company domain
            filter_chain=filter_chain,
            url_scorer=keyword_scorer,
        ),
        cache_mode=CacheMode.BYPASS,
        stream=True,
        verbose=True,
    )
    browser_cfg = BrowserConfig(headless=True, verbose=False)
    metadata: List[dict] = []
    crawled_urls: List[dict] = []

    # 4) Execute crawl
    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        try:
            # a) Await the coroutine to get the async generator
            result_stream = await crawler.arun(url=start_url, config=deep_crawl_cfg)

            # b) Now iterate asynchronously over each result
            async for result in result_stream:
                if not result.success:
                    log.warning(f"Failed to crawl {result.url}")
                    continue

                # Store URL metadata for later extraction
                url_info = {
                    "url": result.url,
                    "depth": result.metadata.get("depth", 0),
                    "score": result.metadata.get("score", 0),
                    "parent_url": result.metadata.get("parent_url"),
                    "title": getattr(result, "title", ""),
                    "success": result.success,
                    "status_code": getattr(result, "status_code", None),
                }
                metadata.append(url_info)
                if getattr(result, "status_code") == 200:
                    crawled_urls.append(
                        {
                            "url": result.url,
                            "score": result.metadata.get("score", 0),
                        }
                    )

                log.debug(
                    f"Discovered URL: {result.url}"
                    f"(depth {result.metadata.get('depth')},"
                    f"score {result.metadata.get('score', 0):.2f})"
                )
        except Exception:
            log.exception(f"Error discovering URLs from {start_url}")

    log.info(f"Discovered {len(metadata)} URLs from {start_url}")

    output_file = f"discovered_urls_{mode}_{urlparse(start_url).netloc}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    log.info(f"Saved discovered URLs to {output_file}")
    return crawled_urls


@tool(
    name="web_crawl",
    description="Web crawling tool",
    show_result=True,
)
async def crawl_tool(start_url: str, mode: str) -> str:
    """
    Crawl a website to find relevant URLs.

    Args:
        start_url (str): The URL to start crawling from.
        mode (str): The extraction mode ('product' or 'revenue').
    """
    try:
        crawled_urls = await crawl4ai_deep_crawl(start_url, mode)
        return json.dumps(
            {
                "crawled_urls": crawled_urls,
            },
            cls=CustomJSONEncoder,
            indent=2,
        )
    except Exception as e:
        log.exception(f"Failed to process {start_url}")
        return json.dumps(
            {
                "success": False,
                "url": start_url,
                "mode": mode,
                "error": str(e),
                "results": [],
            },
            cls=CustomJSONEncoder,
            indent=2,
        )
