import logging

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.wikipedia import WikipediaTools
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)


def main():
    agent = Agent(
        model=OpenAIChat(id="gpt-4.1-mini"),
        tools=[WikipediaTools()],
        description=["You are a researcher specializing in searching Wikipedia."],
        show_tool_calls=True,
        markdown=True,
    )
    agent.print_response("Search Wikipedia for Apple's product line.", markdown=True)


if __name__ == "__main__":
    main()
