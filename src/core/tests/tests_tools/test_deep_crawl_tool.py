import asyncio
import json
import logging

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv

from core.models.websites import CrawledPageList
from core.tools.deep_crawl_tool import deep_crawl_tool

load_dotenv()
log = logging.getLogger(__name__)

url = "https://www.apple.com/newsroom/2025/03/apple-introduces-the-new-macbook-air-with-the-m4-chip-and-a-sky-blue-color/"


async def main():
    crawl_agent = Agent(
        model=OpenAIChat(id="gpt-4.1-nano"),
        tools=[deep_crawl_tool],
        instructions=["Use the web crawling tool tool to find relevant URLs"],
        parser_model=OpenAIChat(id="gpt-4.1-nano"),
        response_model=CrawledPageList,
        show_tool_calls=True,
        markdown=False,
    )

    message = f"Crawl '{url}' using the crawl tool with mode = 'product'"

    # Run the agent
    crawl_resp = await crawl_agent.arun(message)

    # Print the response
    print("\n=== Agent Response ===")
    print(json.dumps(crawl_resp.content.model_dump(), indent=2))

    if crawl_resp.tools:
        log.debug("\n=== Raw Tool Results ===")
        for tool_execution in crawl_resp.tools:
            log.debug(f"Tool: {tool_execution.tool_name}")
            log.debug(f"Result: {tool_execution.result}")


if __name__ == "__main__":
    asyncio.run(main())
