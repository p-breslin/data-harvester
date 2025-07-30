import asyncio
import json
import logging

from agno.utils.pprint import pprint_run_response

from core.agents.base import create_agent
from core.models import (
    DomainProducts,
    ProductLine,
    ProductLineList,
    SeededProductLine,
    SeededProductLineList,
)
from core.tools import extract_tool, search_tool, seed_tool
from core.utils.helpers import load_yaml
from core.utils.logger import setup_logging

setup_logging()
log = logging.getLogger(__name__)
cfg = load_yaml("product_line")


async def main():
    # Search for product lines (sync tool via async API)
    search_agent = create_agent(
        cfg=cfg["product_line_agent_search"],
        tools=[search_tool],
        response_model=DomainProducts,
    )

    N = 5
    company = "Apple"
    search_trigger = json.dumps({"company": company, "N": N})

    # note: arun works even if the tool itself is sync
    search_resp = await search_agent.arun(search_trigger)
    print(f"\nProduct lines for {company}:")
    pprint_run_response(search_resp, markdown=True)

    # Seed product line URLs (async tool)
    seed_agent = create_agent(
        cfg=cfg["product_line_agent_seed"],
        tools=[seed_tool],
        response_model=SeededProductLine,
    )

    domain = search_resp.content.domain
    product_lines = search_resp.content.products

    # Build one JSON trigger per product
    triggers = [
        json.dumps({"domain": domain, "query": [prod]}) for prod in product_lines
    ]

    # Initiate N agent calls in parallel
    seed_resp = await asyncio.gather(*(seed_agent.arun(t) for t in triggers))
    seeded_items = [resp.content for resp in seed_resp]
    seeded_list = SeededProductLineList(domain=domain, results=seeded_items)

    print("\nSeeded product line URLs:")
    print(seeded_list.model_dump_json(indent=2))

    extract_agent = create_agent(
        cfg=cfg["product_line_agent_extract"],
        tools=[extract_tool],
        response_model=ProductLineList,
    )

    # Collect URLs from seeded product lines
    urls = [item.url for item in seeded_items if item.url is not None]

    # Convert schema to JSON string for extraction input
    schema_json = json.dumps(ProductLine.model_json_schema(), indent=2)

    extract_trigger = json.dumps(
        {
            "urls": urls,
            "schema_json": schema_json,
        }
    )

    extract_resp = await extract_agent.arun(extract_trigger)

    print("\nExtracted product line structures:")
    pprint_run_response(extract_resp, markdown=True)


if __name__ == "__main__":
    asyncio.run(main())
