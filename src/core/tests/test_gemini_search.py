from agno.agent import Agent
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv
from models.websites import WebPageList
from utils.helpers import load_yaml

load_dotenv()
company = "Apple"
queries = load_yaml("product_info", key="primary_search_queries")
queries = [q.replace("{company_name}", company) for q in queries]

search_agent = Agent(
    model=Gemini(id="gemini-2.5-flash", grounding=False, search=True),
    parser_model=OpenAIChat(id="gpt-4.1-nano"),
    response_model=WebPageList,
    show_tool_calls=True,
)
search_agent.print_response(
    f"Obtain the top result for each of the following search queries:\n{'\n'.join(queries)}",
    markdown=False,
)
