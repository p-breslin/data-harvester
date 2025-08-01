import logging

from agno.workflow.v2.types import StepInput, StepOutput
from dotenv import load_dotenv

from core.database.arango_handler import ArangoStorageHandler
from core.database.sqlite_handler import SqliteStorageHandler
from core.models import ProductLineList
from core.utils.helpers import load_yaml, save_workflow_output

load_dotenv()
log = logging.getLogger(__name__)

runtime = load_yaml("product_line", key="runtime")


async def profile_sql_storage(step_input: StepInput) -> StepOutput:
    """Stores the generated company profile in the local SQLite database.

    This step receives a validated CompanyProfile object and writes it to a dedicated `company_profiles` table linked to the `companies` table.
    """
    profile = step_input.previous_step_content
    handler = SqliteStorageHandler()
    handler.store_company_profile(profile.model_dump())

    msg = f"SQLite: Stored profile for {profile.company_name}"
    step_output = StepOutput(
        step_name=runtime["profile_sql"], content=msg, success=True
    )
    save_workflow_output(step_output, step_input.additional_data["output_path"])
    return step_output


async def profile_graph_storage(step_input: StepInput) -> StepOutput:
    """Stores profile metadata as attributes on an ArangoDB OrganizationUnit node.

    The company profile is embedded into the node representing the company, using the CIK as the node key.
    """
    profile = step_input.previous_step_content
    handler = ArangoStorageHandler()
    handler.store_company_profile(profile.model_dump())

    msg = f"ArangoDB: Stored profile for {profile.company_name}"
    step_output = StepOutput(
        step_name=runtime["profile_graph"], content=msg, success=True
    )
    save_workflow_output(step_output, step_input.additional_data["output_path"])
    return step_output


async def pl_sql_storage(step_input: StepInput) -> StepOutput:
    """Stores extracted product line data in the SQLite database.

    This step writes the structured ProductLineList to a `product_lines` table, associating each product line with the appropriate company ID.
    """
    results: ProductLineList = step_input.previous_step_content
    handler = SqliteStorageHandler()
    count = handler.store_product_lines(
        {
            "company_name": results.company_name,
            "product_lines": [pl.model_dump() for pl in results.product_lines],
        }
    )

    msg = f"Stored {count} product lines for {results.company_name}"
    step_output = StepOutput(step_name=runtime["pl_sql"], content=msg, success=True)
    save_workflow_output(
        step_output=step_output,
        output_path=step_input.additional_data["output_path"],
    )
    return step_output


async def pl_graph_storage(step_input: StepInput) -> StepOutput:
    """Creates DomainEntity nodes for each product line and links them to the company node in ArangoDB.

    The product lines are fetched from the SQLite database and stored in the graph using PartOfProduct edges connecting them to the OrganizationUnit representing the company.
    """
    company_name = step_input.additional_data["company_name"]
    handler = ArangoStorageHandler()
    count = handler.store_product_lines(company_name)

    msg = f"Processed company '{company_name}' with {count} product lines in ArangoDB"
    step_output = StepOutput(step_name=runtime["pl_graph"], content=msg, success=True)
    save_workflow_output(
        step_output=step_output,
        output_path=step_input.additional_data["output_path"],
    )
    return step_output
