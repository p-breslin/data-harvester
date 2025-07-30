import json
import os

from agno.tools import tool
from dotenv import load_dotenv
from tavily import TavilyClient

from core.utils.logger import log_tools


@tool(
    name="search_tool",
    description="Tool for searching the internet",
    show_result=True,
)
def search_tool(query: str) -> str:
    """Searches the web for information using Tavily's search API.

    Args:
        query (str): The search query

    Returns:
        str: JSON string containing search results.
    """
    load_dotenv()
    search_log = log_tools("search_tool")
    try:
        # Initialize Tavily client
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not tavily_api_key:
            return json.dumps(
                {
                    "error": "TAVILY_API_KEY environment variable not set",
                    "query": query,
                    "results": [],
                }
            )

        client = TavilyClient(api_key=tavily_api_key)

        # Perform search
        search_log.debug(f"Search query: {query}")
        response = client.search(
            query=query,
            max_results=5,
            time_range="year",
            search_depth="basic",
            include_answer=False,
            include_raw_content=False,
        )

        # Format results
        results = []
        for result in response.get("results", []):
            entry = {
                "url": result.get("url", ""),
                "title": result.get("title", ""),
                "content": result.get("content", ""),
            }
            search_log.debug(json.dumps(entry, indent=2))
            results.append(entry)
        return json.dumps({"results": results}, indent=2)

    except Exception as e:
        return json.dumps(
            {"error": f"Search failed: {str(e)}", "query": query, "results": []}
        )
