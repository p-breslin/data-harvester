import asyncio
import json
import logging

from dotenv import load_dotenv

from core.agents.base import create_agent
from core.models import NodePayloadList
from core.utils.helpers import load_yaml
from core.utils.logger import setup_logging

from .test_sql_handler import InternalDB

load_dotenv()
setup_logging()
log = logging.getLogger(__name__)
cfg = load_yaml("product_line")  # Configuration file

profile = {
    "Company profile": {
        "company_name": "Apple Inc.",
        "ticker": "AAPL",
        "cik": 320193,
        "industry": "Electronic Computers",
        "location": "CUPERTINO, CA",
        "sic_code": "3571",
        "fiscal_year_end": "0927",
        "web_site": "https://www.apple.com/",
        "exchanges": ["Nasdaq"],
        "shares_outstanding": 14840390000.0,
        "public_float": 2628553000000.0,
        "latest_revenue": "$6,541,000,000 (2024-06-29)",
    }
}

product_lines = {
    "company_name": "Apple Inc.",
    "product_lines": [
        {
            "name": "iPhone",
            "type": "product",
            "description": "Apple's line of smartphones, offering advanced performance, camera technology, and iOS integration.",
            "category": "Smartphones",
        },
        {
            "name": "iPad",
            "type": "product",
            "description": "Apple's family of tablets, designed for productivity, creativity, and entertainment.",
            "category": "Tablets",
        },
    ],
}


async def transform_and_store(agent, db: InternalDB, raw_data: dict):
    """Runs the full transform and store process for a given piece of raw data.

    1. Triggers the agent to transform the data.
    2. Validates the agent's response.
    3. Stores the resulting payloads in the database.
    """
    log.info("Processing raw data...")
    trigger = json.dumps(raw_data, indent=2)

    # Run the agent
    resp = await agent.arun(trigger)
    payload = resp.content

    try:
        log.info("Transformed data into %d payloads.", len(payload.payloads))
        log.debug("Transformed data:\n%s", payload.model_dump_json(indent=2))

        db.upsert_payloads(payload.payloads)
        log.info("Stored %d payloads.", len(payload.payloads))

    except Exception as e:
        log.error("Failed to process agent response. Error: %s", e)
        log.error("Raw agent response content:\n%s", payload.model_dump_json(indent=2))


async def main():
    agent = create_agent(cfg=cfg["agent_transform"], response_model=NodePayloadList)

    # Instantiate the database
    db = InternalDB()
    log.info("InternalDB instance created. Path: %s", db.db_path)

    # Process each piece of data
    await transform_and_store(agent, db, profile)
    await transform_and_store(agent, db, product_lines)
    log.info("All processing complete.")

    log.info("Qeurying the database...")
    db_contents = db.query_database()
    print(json.dumps(db_contents, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
