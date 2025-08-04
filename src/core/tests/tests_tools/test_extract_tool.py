import asyncio
import json
import logging

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.utils.pprint import pprint_run_response
from dotenv import load_dotenv

from core.models.products import ProductList
from core.tools import extract_tool
from core.utils.helpers import load_yaml, validate_response
from core.utils.logger import setup_logging

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

cfg = load_yaml("agents", key="extract")
urls = [
    "https://www.apple.com/ipad-mini/",
    "https://www.apple.com/macbook-pro/",
]
schema_json = ProductList.model_json_schema()  # serialize schema for tool
instructions = cfg["instructions"].format(
    schema=json.dumps(schema_json, indent=2), urls=json.dumps(urls, indent=2)
)


async def main():
    agent = Agent(
        name=cfg["name"],
        role=cfg["role"],
        description=cfg["description"],
        instructions=instructions,
        model=OpenAIChat(id=cfg["model_id"]),
        parser_model=OpenAIChat(id=cfg["parser_model_id"]),
        tools=[extract_tool],
        response_model=ProductList,
        show_tool_calls=True,
        markdown=cfg["markdown"],
    )
    response = await agent.arun("Extract the data as instructed.")
    pprint_run_response(response, markdown=False)
    validate_response(response.content, ProductList, savefile="test_llm_extract")


if __name__ == "__main__":
    asyncio.run(main())
