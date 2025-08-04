import logging
from typing import Type, Union

from agno.workflow.v2.types import StepInput, StepOutput
from dotenv import load_dotenv
from pydantic import BaseModel

from core.database.arango_handler import ArangoStorageHandler
from core.database.sqlite_handler import SqliteStorageHandler
from core.models import CompanyProfile, ProductLineList
from core.utils.helpers import load_yaml, save_workflow_output

load_dotenv()
log = logging.getLogger(__name__)

runtime = load_yaml("product_line", key="runtime")


def _parse_step_content(
    content: Union[str, BaseModel], model_cls: Type[BaseModel]
) -> BaseModel:
    """Ensures that `content` is an instance of `model_cls`.

    If it's a JSON string, parse it via Pydantic; otherwise return as-is.
    """
    if isinstance(content, str):
        return model_cls.model_validate_json(content)
    if isinstance(content, model_cls):
        return content
    raise TypeError(
        f"Expected {model_cls.__name__} or JSON str, got {type(content).__name__}"
    )


async def profile_sql_storage(step_input: StepInput) -> StepOutput:
    """Stores the generated company profile in the local SQLite database.

    This step receives a validated CompanyProfile object and writes it to a dedicated `company_profiles` table linked to the `companies` table.
    """
    profile = _parse_step_content(step_input.previous_step_content, CompanyProfile)
    handler = SqliteStorageHandler()
    handler.store_company_profile(profile.model_dump())

    log.info(f"SQLite: Stored profile for {profile.company_name}")
    step_output = StepOutput(
        step_name=runtime["profile_sql"],
        content=profile.model_dump_json(),
        success=True,
    )
    save_workflow_output(step_output, step_input.additional_data["output_path"])
    return step_output


async def profile_graph_storage(step_input: StepInput) -> StepOutput:
    """Stores profile metadata as attributes on an ArangoDB OrganizationUnit node.

    The company profile is embedded into the node representing the company, using the pre-generated UUID as the node key.
    """
    profile = _parse_step_content(step_input.previous_step_content, CompanyProfile)
    handler = ArangoStorageHandler()

    key = step_input.additional_data["org_unit_key"]
    handler.store_company_profile(profile.model_dump(), key=key)

    log.info(f"ArangoDB: Stored profile for {profile.company_name}")
    step_output = StepOutput(
        step_name=runtime["profile_graph"],
        content=profile.model_dump_json(),
        success=True,
    )
    save_workflow_output(step_output, step_input.additional_data["output_path"])
    return step_output


async def pl_sql_storage(step_input: StepInput) -> StepOutput:
    """Stores extracted product line data in the SQLite database.

    This step writes the structured ProductLineList to a `product_lines` table, associating each product line with the appropriate company ID.
    """
    res = _parse_step_content(step_input.previous_step_content, ProductLineList)
    handler = SqliteStorageHandler()
    count = handler.store_product_lines(
        {
            "company_name": res.company_name,
            "product_lines": [pl.model_dump() for pl in res.product_lines],
        }
    )

    log.info(f"Stored {count} product lines for {res.company_name}")
    step_output = StepOutput(step_name=runtime["pl_sql"], content=res, success=True)
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

    key = step_input.additional_data["org_unit_key"]
    count = handler.store_product_lines(company_name, key=key)

    log.info(f"Processed '{company_name}' with {count} product lines in ArangoDB")
    step_output = StepOutput(
        step_name=runtime["pl_graph"],
        content={"company_name": company_name, "count": count},
        success=True,
    )
    save_workflow_output(
        step_output=step_output,
        output_path=step_input.additional_data["output_path"],
    )
    return step_output
