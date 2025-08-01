import asyncio

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv

from core.models import CompanyProfile
from core.tools import search_tool, sec_tool
from core.utils.logger import setup_logging

load_dotenv()
setup_logging()

description = "An agent that builds an SEC company profile"
instructions = [
    "Use search_tool to look up the ticker symbol for the provided company name if you don't already know it.",
    "Invoke the SEC tool with the ticker symbol to fetch the company's SEC profile.",
]


async def main():
    agent = Agent(
        model=OpenAIChat(id="gpt-4.1-mini"),
        tools=[search_tool, sec_tool],
        description=description,
        instructions=instructions,
        response_model=CompanyProfile,
        parser_model=OpenAIChat(id="gpt-4.1-nano"),
        show_tool_calls=True,
        markdown=True,
    )

    prompt = (
        "Return a company profile for Apple. "
        "If you don't know Apple's ticker, use the search tool to find it, "
        "then call the SEC tool to fetch and return the profile."
    )
    await agent.aprint_response(prompt, markdown=True)


if __name__ == "__main__":
    asyncio.run(main())
