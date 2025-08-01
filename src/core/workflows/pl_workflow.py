import asyncio
import json
import logging
from datetime import datetime

from agno.storage.sqlite import SqliteStorage
from agno.workflow.v2 import Step, Workflow
from agno.workflow.v2.types import StepInput, StepOutput

from core.agents.base import create_agent
from core.models import (
    CompanyProfile,
    DomainProducts,
    ProductLine,
    ProductLineList,
    SeededProductLine,
    SeededProductLineList,
)
from core.tools import extract_tool, search_tool, sec_tool, seed_tool
from core.utils.helpers import load_yaml, save_workflow_output
from core.utils.logger import setup_logging
from core.utils.paths import DATA_DIR
from core.workflows.storage_steps import (
    pl_graph_storage,
    pl_sql_storage,
    profile_graph_storage,
    profile_sql_storage,
)

# --- Set up ---------------------------------------------------------------------------

setup_logging()
log = logging.getLogger(__name__)

# Configuration file
cfg = load_yaml("product_line")

# Save path for workflow output
execution_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
output_path = DATA_DIR / "workflow_outputs" / execution_time
output_path.mkdir(parents=True, exist_ok=True)


# --- Agents ---------------------------------------------------------------------------


async def profile_step(step_input: StepInput) -> StepOutput:
    """Generates a structured company profile.

    Spawns an Agno agent with SEC and search tools to retrieve company profile information. The output conforms to the CompanyProfile predefined schema.
    """

    # Initiate the agent
    profile_agent = create_agent(
        cfg=cfg["agent_company_profile"],
        tools=[search_tool, sec_tool],
        response_model=CompanyProfile,
    )

    # Run the agent
    company = step_input.message["company"]
    trigger = json.dumps({"company": company})
    resp = await profile_agent.arun(trigger)

    # Process the workflow step
    step_output = StepOutput(
        step_name=cfg["runtime"]["profile"],
        content=resp.content,
        success=True,
    )
    save_workflow_output(
        step_output=step_output,
        output_path=step_input.additional_data["output_path"],
    )
    return step_output


async def search_step(step_input: StepInput) -> StepOutput:
    """Searches for high-level product or service lines associated with a company.

    Spawns an Agno agent with a web search tool to identify N product or service lines for a given company official sources. The output conforms to the DomainProducts predefined schema.
    """
    # Initiate the agent
    search_agent = create_agent(
        cfg=cfg["agent_search"],
        tools=[search_tool],
        response_model=DomainProducts,
    )

    # Run the agent
    company = step_input.message["company"]
    N = step_input.message["N"]
    trigger = json.dumps({"company": company, "N": N})
    resp = await search_agent.arun(trigger)

    # Process workflow step
    step_output = StepOutput(
        step_name=cfg["runtime"]["search"],
        content=resp.content,  # DomainProducts object
        success=True,
    )
    save_workflow_output(
        step_output=step_output,
        output_path=step_input.additional_data["output_path"],
    )
    return step_output


async def seed_step(step_input: StepInput) -> StepOutput:
    """Seeds product lines with candidate URLs for structured extraction.

    Spawns parallelized Agno agents with a URL seed tool to find representative URLs for each provided product line. The output conforms to the SeededProductLine predefined schema.
    """
    # Initiate the agent
    seed_agent = create_agent(
        cfg=cfg["agent_seed"],
        tools=[seed_tool],
        response_model=SeededProductLine,
    )

    # Prepare input from output of Search Step
    search_output = step_input.previous_step_content
    domain = search_output.domain
    products = search_output.products

    # Parallel execution - build triggers for each instance of the seed agent
    triggers = [json.dumps({"domain": domain, "query": [prod]}) for prod in products]

    # Run the agents in parallel
    resp = await asyncio.gather(*(seed_agent.arun(t) for t in triggers))
    seeded_items = [resp.content for resp in resp]
    seeded_list = SeededProductLineList(domain=domain, product_line_urls=seeded_items)

    # Process workflow step
    step_output = StepOutput(
        step_name=cfg["runtime"]["seed"],
        content=seeded_list,
        success=True,
    )
    save_workflow_output(
        step_output=step_output,
        output_path=step_input.additional_data["output_path"],
    )
    return step_output


async def extract_step(step_input: StepInput) -> StepOutput:
    """Extracts structured product line data from the seeded URLs.

    Spawns an Agno agent with a data extraction (web crawling and scraping) tool to extract product line information from product-line-specific URLs. The output conforms to the ProductLineList predefined schema.
    """

    # Initiate the agent
    extract_agent = create_agent(
        cfg=cfg["agent_extract"],
        tools=[extract_tool],
        response_model=ProductLineList,
    )

    # Prepare input from output of Seed Step
    seed_output = step_input.previous_step_content
    urls = [item.url for item in seed_output.product_line_urls if item.url is not None]

    # Convert schema to JSON string for extraction input (specific to extract tool)
    schema_json = json.dumps(ProductLine.model_json_schema(), indent=2)

    # Run the agent
    trigger = json.dumps({"urls": urls, "schema_json": schema_json})
    resp = await extract_agent.arun(trigger)

    # Process workflow step
    step_output = StepOutput(
        step_name=cfg["runtime"]["extract"],
        content=resp.content,
        success=True,
    )
    save_workflow_output(
        step_output=step_output,
        output_path=step_input.additional_data["output_path"],
    )
    return step_output


# --- Workflow Execution ---------------------------------------------------------------


async def main():
    """Orchestrates the end-to-end product profiling Agno workflow for a target company.

    This function sets up and executes a multi-step workflow that:
      1. Generates a structured company profile from SEC and web search data.
      2. Stores the profile in both SQLite and ArangoDB.
      3. Discovers the company's public product lines via web search.
      4. Seeds each product line with representative URLs.
      5. Extracts structured product information from those URLs.
      6. Stores the extracted product line data in both SQLite and ArangoDB.

    Workflow configuration is loaded from a YAML file, and runtime outputs are persisted to a timestamped directory for later inspection.
    """
    runtime = cfg["runtime"]
    product_workflow = Workflow(
        name=runtime["name"],
        description=runtime["description"],
        storage=SqliteStorage(
            table_name=runtime["table_name"],
            db_file=runtime["db_file"],
            mode="workflow_v2",
        ),
        steps=[
            # Company Profile -> Storage
            Step(name=runtime["profile"], executor=profile_step),
            Step(name=runtime["profile_sql"], executor=profile_sql_storage),
            Step(name=runtime["profile_graph"], executor=profile_graph_storage),
            # Product Lines -> Storage
            Step(name=runtime["search"], executor=search_step),
            Step(name=runtime["seed"], executor=seed_step),
            Step(name=runtime["extract"], executor=extract_step),
            Step(name=runtime["pl_sql"], executor=pl_sql_storage),
            Step(name=runtime["pl_graph"], executor=pl_graph_storage),
        ],
    )
    trigger = {"company": runtime["company"], "N": runtime["N_product_lines"]}
    workflow_success = True

    # Run the workflow and iterate over the stream
    async for event in await product_workflow.arun(
        message=trigger,
        additional_data={
            "output_path": output_path,
            "company_name": runtime["company"],
        },
        stream=True,
    ):
        # Process events as they come
        if hasattr(event, "content") and event.content:
            if hasattr(event, "step_name"):
                # step-level event
                print(f"Event: {type(event).__name__} - Step: {event.step_name}")
            else:
                # workflow-level event
                print(
                    f"Event: {type(event).__name__} - Workflow: {getattr(event, 'workflow_name', 'Unknown Workflow')}"
                )

        if getattr(event, "success", None) is not True:
            workflow_success = False
    if workflow_success:
        print("\nWorkflow completed successfully.")
    else:
        print("\nWorkflow encountered errors.")


if __name__ == "__main__":
    asyncio.run(main())
