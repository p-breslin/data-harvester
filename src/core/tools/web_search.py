import json
import os

from agno.tools import tool
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()


@tool(
    name="web_search",
    description="Tool for searching the internet",
    show_result=True,
)
def search_tool(query: str) -> str:
    """Searches the web for information using Tavily's search API.

    Args:
        query (str): The search query

    Returns:
        str: JSON string containing search results (URL and title)
    """
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
            results.append(
                {
                    "url": result.get("url", ""),
                    "title": result.get("title", ""),
                }
            )

        return json.dumps(
            {
                "results": results,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {"error": f"Search failed: {str(e)}", "query": query, "results": []}
        )
