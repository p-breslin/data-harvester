import asyncio
import json
import logging
import os
from datetime import datetime

from agno.storage.sqlite import SqliteStorage
from agno.workflow.v2 import Step, Workflow
from agno.workflow.v2.types import StepInput, StepOutput
from dotenv import load_dotenv
from xflow_graph.adapters.arango import ArangoAdapter
from xflow_graph.models import create_model_instance, generate_document_id
from xflow_graph.services.graph import GraphService

from core.agents.base import create_agent
from core.clients.arango import ArangoManager
from core.clients.sqlite import get_connection
from core.database.sqlite_db import CompanyDataDB
from core.models import (
    DomainProducts,
    ProductLine,
    ProductLineList,
    SeededProductLine,
    SeededProductLineList,
)
from core.tools import extract_tool, search_tool, seed_tool
from core.utils.helpers import load_yaml, save_workflow_output
from core.utils.logger import setup_logging
from core.utils.paths import DATA_DIR

load_dotenv()
setup_logging()
log = logging.getLogger(__name__)

cfg = load_yaml("product_line")

# Set-up for workflow output save files
execution_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
output_path = DATA_DIR / "workflow_outputs" / execution_time
output_path.mkdir(parents=True, exist_ok=True)


async def search_step_function(step_input: StepInput) -> StepOutput:
    """Search for product lines using the search agent"""
    # Parse input parameters
    input_data = (
        json.loads(step_input.message)
        if isinstance(step_input.message, str)
        else step_input.message
    )
    company = input_data.get("company", "Apple")
    N = input_data.get("N", 5)

    # Search agent
    search_agent = create_agent(
        cfg=cfg["product_line_agent_search"],
        tools=[search_tool],
        response_model=DomainProducts,
    )

    # Execute search
    search_trigger = json.dumps({"company": company, "N": N})
    search_resp = await search_agent.arun(search_trigger)
    step_output = StepOutput(
        step_name="Search",
        content=search_resp.content,  # DomainProducts object
        success=True,
    )
    save_workflow_output(step_output=step_output, output_path=output_path)
    return step_output


async def parallel_seeding_step(step_input: StepInput) -> StepOutput:
    """Parallel seeding step that preserves the asyncio.gather() pattern"""

    search_results = step_input.previous_step_content  # previous results
    if not isinstance(search_results, DomainProducts):
        raise ValueError("Expected DomainProducts from search step")

    domain = search_results.domain
    product_lines = search_results.products

    # Seed agent
    seed_agent = create_agent(
        cfg=cfg["product_line_agent_seed"],
        tools=[seed_tool],
        response_model=SeededProductLine,
    )

    # Build triggers for each instance of the seed agent
    triggers = [
        json.dumps({"domain": domain, "query": [prod]}) for prod in product_lines
    ]

    # Parallel execution
    seed_resp = await asyncio.gather(*(seed_agent.arun(t) for t in triggers))
    seeded_items = [resp.content for resp in seed_resp]
    seeded_list = SeededProductLineList(domain=domain, results=seeded_items)

    step_output = StepOutput(
        step_name="Parallel Seeding", content=seeded_list, success=True
    )
    save_workflow_output(step_output=step_output, output_path=output_path)
    return step_output


async def extract_step_function(step_input: StepInput) -> StepOutput:
    """Extract structured data from seeded URLs"""

    seeded_results = step_input.previous_step_content  # previous results
    if not isinstance(seeded_results, SeededProductLineList):
        raise ValueError("Expected SeededProductLineList from seeding step")

    # Extract agent
    extract_agent = create_agent(
        cfg=cfg["product_line_agent_extract"],
        tools=[extract_tool],
        response_model=ProductLineList,
    )

    # Collect URLs from seeded product lines
    urls = [item.url for item in seeded_results.results if item.url is not None]

    # Convert schema to JSON string for extraction input
    schema_json = json.dumps(ProductLine.model_json_schema(), indent=2)

    extract_trigger = json.dumps(
        {
            "urls": urls,
            "schema_json": schema_json,
        }
    )

    extract_resp = await extract_agent.arun(extract_trigger)
    step_output = StepOutput(
        step_name="Extract", content=extract_resp.content, success=True
    )
    save_workflow_output(step_output=step_output, output_path=output_path)
    return step_output


async def db_storage_step(step_input: StepInput) -> StepOutput:
    """Store extracted product lines in database"""

    extract_results = step_input.previous_step_content
    if not isinstance(extract_results, ProductLineList):
        raise ValueError("Expected ProductLineList from extract step")

    # Convert to dict format
    product_data = {
        "company_name": extract_results.company_name,
        "product_lines": [
            {
                "name": pl.name,
                "type": pl.type,
                "description": pl.description,
                "category": pl.category,
            }
            for pl in extract_results.product_lines
        ],
    }

    # Initialize database and store data
    db = CompanyDataDB()
    db.insert_product_lines(product_data)

    step_output = StepOutput(
        step_name="Database Storage",
        content=f"Stored {len(product_data['product_lines'])} product lines for {product_data['company_name']}",
        success=True,
    )
    save_workflow_output(step_output=step_output, output_path=output_path)
    return step_output


async def arango_step(step_input: StepInput) -> StepOutput:
    conn = get_connection()  # connect to SQLite

    # Check if the Arango database exists
    manager = ArangoManager()
    db_name = os.getenv("ARANGO_DB")
    if not manager.exists(db_name):
        manager.create(db_name)

    # Initialize Arango adapter and graph service
    adapter = ArangoAdapter.connect()
    service = GraphService(adapter)

    # Fetch all companies
    companies = conn.execute("SELECT id, name FROM companies ORDER BY name").fetchall()
    if not companies:
        log.warning("No companies found in the database.")
        return

    for comp in companies:
        # Upsert company node
        comp_key = generate_document_id().replace("-", "")[:16]
        comp_id = f"OrganizationUnit/{comp_key}"
        comp_doc = create_model_instance(
            "OrganizationUnit",
            {"_key": comp_key, "name": comp["name"], "sub_type": "Company"},
        )
        service.upsert_node("OrganizationUnit", comp_doc)

        # Fetch product lines for this company
        sql = (
            "SELECT id, name, type, description, category "
            "FROM product_lines "
            "WHERE company_id = ? "
            "ORDER BY name"
        )
        rows = conn.execute(sql, (comp["id"],)).fetchall()
        if not rows:
            log.warning(
                f"No product lines for company '{comp['name']}' (ID {comp['id']})."
            )
            continue

        node_ops = []
        edge_docs = []
        for r in rows:
            # Create product node
            prod_key = generate_document_id().replace("-", "")[:16]
            prod_id = f"DomainEntity/{prod_key}"
            node_doc = create_model_instance(
                "DomainEntity",
                {
                    "_key": prod_key,
                    "name": r["name"],
                    "sub_type": r["category"] or "",
                    "attributes": {"description": r["description"] or ""},
                },
            )
            node_ops.append({"collection": "DomainEntity", "doc": node_doc})

            # Create PartOfProduct edge
            edge_data = create_model_instance(
                "PartOfProduct",
                {"source_id": comp_id, "target_id": prod_id},
                is_edge=True,
            )
            edge_fmt = {
                **edge_data.model_dump(),
                "_from": edge_data.source_id,
                "_to": edge_data.target_id,
            }
            edge_docs.append(edge_fmt)

        # Batch upsert nodes and link edges for this company
        service.batch_upsert_nodes(node_ops, use_transaction=False)
        service.link_edges("PartOfProduct", edge_docs)

        step_output = StepOutput(
            step_name="ArangoDB Storage",
            content=f"Processed company '{comp['name']}' with {len(rows)} product lines.",
            success=True,
        )
    save_workflow_output(step_output=step_output, output_path=output_path)
    return step_output


async def main():
    runtime = cfg["product_line_runtime"]
    product_workflow = Workflow(
        name=runtime["name"],
        description=runtime["description"],
        storage=SqliteStorage(
            table_name=runtime["table_name"],
            db_file=runtime["db_file"],
            mode="workflow_v2",
        ),
        steps=[
            Step(name="Search", executor=search_step_function),
            Step(name="Parallel Seeding", executor=parallel_seeding_step),
            Step(name="Extract", executor=extract_step_function),
            Step(name="Database Storage", executor=db_storage_step),
            Step(name="ArangoDB Storage", executor=arango_step),
        ],
    )
    trigger = {"company": runtime["company"], "N": runtime["N_product_lines"]}

    # Run the workflow and iterate over the stream
    async for event in await product_workflow.arun(
        message=json.dumps(trigger), stream=True
    ):
        # Process events as they come
        if hasattr(event, "content") and event.content:
            if hasattr(event, "step_name"):
                # This is a step-level event
                print(f"Event: {type(event).__name__} - Step: {event.step_name}")
            else:
                # This is a workflow-level event
                print(
                    f"Event: {type(event).__name__} - Workflow: {getattr(event, 'workflow_name', 'Unknown Workflow')}"
                )

    print("\nWorkflow completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
