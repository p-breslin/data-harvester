from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.wikipedia import WikipediaTools
from dotenv import load_dotenv
from langfuse import observe

load_dotenv()


@observe()
def wikisearch():
    agent = Agent(
        model=OpenAIChat(id="gpt-4.1-mini"),
        tools=[WikipediaTools()],
        description=["You are a researcher specializing in searching Wikipedia."],
        show_tool_calls=True,
        markdown=True,
    )
    agent.print_response(
        "Search Wikipedia for Apple's best selling product.", markdown=True
    )


wikisearch()
