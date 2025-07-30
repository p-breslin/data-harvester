import asyncio

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv

from core.models import SeededUrlList
from core.tools import seed_tool
from core.utils.logger import setup_logging

load_dotenv()
setup_logging()


async def main():
    agent = Agent(
        model=OpenAIChat(id="gpt-4.1-mini"),
        tools=[seed_tool],
        description=[
            "You are a seed agent specialized in discovering relevant URLs within a domain."
        ],
        response_model=SeededUrlList,
        parser_model=OpenAIChat(id="gpt-4.1-nano"),
        show_tool_calls=True,
        markdown=True,
    )

    # Instruct the agent to invoke the seed tool
    prompt = "Search for iPhone technical specifications on apple.com"
    await agent.aprint_response(prompt, markdown=True)


if __name__ == "__main__":
    asyncio.run(main())
