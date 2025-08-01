import argparse
from datetime import datetime, timedelta

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.googlesearch import GoogleSearchTools
from dotenv import load_dotenv

from core.models.websites import WebPageList
from core.tools import search_tool

load_dotenv()


_DESCRIPTION = "You are a web search agent that searches the user's query."
_INSTRUCTION = [
    "Search the user query exactly.",
    "Make exactly one search tool call.",
    "Return 5 results.",
]


class WebSearch:
    """Uses different web search tools to make web searches."""

    def __init__(self, base_query: str = None):
        # Allow overriding via constructor
        self.base_query = base_query or "Official Apple Product information"
        self.today = datetime.today()

    def get_date_filtered_query(self):
        """Returns query string with 1-year date filtering applied."""
        year_ago = self.today - timedelta(days=365)
        after = year_ago.strftime("%Y-%m-%d")
        before = self.today.strftime("%Y-%m-%d")
        return f"{self.base_query} after:{after} before:{before}"

    def _run_agent_search(
        self,
        *,
        tool,
        query,
        model_id="gpt-4.1-mini",
        parser_id="gpt-4.1-nano",
        markdown=False,
        description=_DESCRIPTION,
        instructions=_INSTRUCTION,
        response_model=WebPageList,
    ):
        """Creates an Agno agent instance customized for web searching."""
        agent = Agent(
            tools=[tool],
            description=description,
            instructions=instructions,
            model=OpenAIChat(id=model_id),
            parser_model=OpenAIChat(id=parser_id),
            response_model=response_model,
            show_tool_calls=True,
        )
        agent.print_response(query, markdown=markdown)

    def tavily_search(self):
        """Custom Tavily web search tool with built in date filtering."""
        self._run_agent_search(
            tool=search_tool,
            query=self.base_query,
        )

    def google_search(self):
        """Agno's built-in Google web search tool."""
        self._run_agent_search(
            tool=GoogleSearchTools(),
            query=self.get_date_filtered_query(),
        )

    def ddg_search(self):
        """Agno's built-in DuckDuckGo web search tool (no date functionality)."""
        self._run_agent_search(
            tool=DuckDuckGoTools(search=True, news=False),
            query=self.base_query,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a specific web search.")
    parser.add_argument(
        "-q",
        "--base-query",
        type=str,
        help="Override the default base query string",
    )
    parser.add_argument("-tavily", action="store_true", help="Run Tavily web search")
    parser.add_argument("-google", action="store_true", help="Run Google web search")
    parser.add_argument("-ddg", action="store_true", help="Run DuckDuckGo web search")

    args = parser.parse_args()
    # Pass the CLI base-query into WebSearch
    search = WebSearch(base_query=args.base_query)

    if args.tavily:
        search.tavily_search()
    elif args.google:
        search.google_search()
    elif args.ddg:
        search.ddg_search()
    else:
        parser.print_help()
