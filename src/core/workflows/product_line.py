import asyncio
import json
import logging
from datetime import datetime

from agno.storage.sqlite import SqliteStorage
from agno.workflow.v2 import Step, Workflow
from agno.workflow.v2.types import StepInput, StepOutput

from core.agents.base import create_agent
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
        ],
    )
    trigger = {"company": runtime["company"], "N": runtime["N_product_lines"]}

    # Run the workflow and iterate over the stream
    async for event in await product_workflow.arun(
        message=json.dumps(trigger), stream=True
    ):
        # Process events as they come
        if hasattr(event, "content") and event.content:
            print(f"Event: {type(event).__name__}")

    print("\nWorkflow completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
