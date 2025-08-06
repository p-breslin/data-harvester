import asyncio
import json
import logging

from agno.workflow.v2.types import StepInput, StepOutput

from core.agents.base import create_agent
from core.models import (
    CompanyProfile,
    DomainProducts,
    NodePayloadList,
    ProductLine,
    ProductLineList,
    SeededProductLine,
    SeededProductLineList,
)
from core.tools import extract_tool, search_tool, sec_tool, seed_tool
from core.utils.helpers import load_yaml, save_workflow_output

log = logging.getLogger(__name__)
cfg = load_yaml("product_line")  # Configuration file


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

    # Pass the canonical company name for the next steps
    step_input.additional_data["canonical_name"] = resp.content.company_name

    # Process the workflow step
    step_output = StepOutput(
        step_name=cfg["runtime"]["profile"],
        content=resp.content,  # Return the raw Pydantic object
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
    company = step_input.additional_data["canonical_name"]
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
    triggers = [json.dumps({"domain": domain, "query": [p]}) for p in products]

    # Run the agents in parallel
    resp = await asyncio.gather(*(seed_agent.arun(t) for t in triggers))
    seeded_items = [r.content for r in resp]
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
    urls = [item.url for item in seed_output.product_line_urls if item.url]

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


async def transform_step(step_input: StepInput) -> StepOutput:
    """Transforms scraped data into the correct format for SQL storage.

    This step passes the raw scraped data object to an agent who transforms it into a list of schemas according to NodePayload for insertion into the SQL database.
    """
    raw_data_object = step_input.previous_step_content

    # Create and run the agent
    transform_agent = create_agent(
        cfg=cfg["agent_transform"],
        response_model=NodePayloadList,
    )
    trigger = raw_data_object.model_dump_json()  # raw data object JSON serialized
    resp = await transform_agent.arun(trigger)

    log.info("Transformed data into %d payloads.", len(resp.content.payloads))
    log.debug("Transformed data:\n%s", resp.content.model_dump_json(indent=2))

    # Process workflow step
    step_output = StepOutput(
        step_name=cfg["runtime"]["transform"],
        content=resp.content,
        success=True,
    )
    save_workflow_output(
        step_output=step_output,
        output_path=step_input.additional_data["output_path"],
    )
    return step_output
