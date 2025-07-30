import asyncio
import json
import logging

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv

from core.models.products import Product
from core.tools import scrape_tool

load_dotenv()
log = logging.getLogger(__name__)


url = "https://www.apple.com/support/products/iphone"


async def main():
    crawl_agent = Agent(
        model=OpenAIChat(id="gpt-4.1-nano"),
        tools=[scrape_tool],
        instructions=[
            "Use the web scraping tool to extract relevant data.",
            "If items from the response model cannot be found, leave it blank.",
        ],
        parser_model=OpenAIChat(id="gpt-4.1-nano"),
        response_model=Product,
        show_tool_calls=True,
        markdown=False,
    )

    message = f"Use the scrape tool with url = {url} and mode = 'product'"

    # Run the agent
    crawl_resp = await crawl_agent.arun(message)
    print("\n=== Agent Response ===")
    print(json.dumps(crawl_resp.content.model_dump(), indent=2))

    if crawl_resp.tools:
        log.debug("\n=== Raw Tool Results ===")
        for tool_execution in crawl_resp.tools:
            log.debug(f"Tool: {tool_execution.tool_name}")
            log.debug(f"Result: {tool_execution.result}")


if __name__ == "__main__":
    asyncio.run(main())
