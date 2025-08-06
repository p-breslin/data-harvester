import logging

from agno.workflow.v2.types import StepInput, StepOutput

from core.models.payloads import NodePayloadList

from .graph_handler import GraphStorageHandler
from .sql_handler import InternalDB

log = logging.getLogger(__name__)


async def store_sql_step(step_input: StepInput, step_name: str) -> StepOutput:
    """Generic Agno workflow step to store a list of entities into SQLiteDB."""
    payload_obj: NodePayloadList = step_input.previous_step_content

    if not payload_obj:
        log.warning("store_sql_step received no payloads to store. Skipping.")
        return StepOutput(
            step_name=step_name,
            content={"success": False},
            success=True,
        )

    handler = InternalDB()
    try:
        handler.upsert_payloads(payload_obj.payloads)
        log.info("Successfully stored entities in SQLite.")
    except Exception as e:
        log.error(f"An error occurred during SQL storage: {e}", exc_info=True)
        return StepOutput(
            step_name=step_name,
            success=False,
            error=str(e),
        )

    return StepOutput(
        step_name=step_name,
        content={"success": True},
        success=True,
    )


async def store_graph_step(step_input: StepInput, step_name: str) -> StepOutput:
    """Generic Agno workflow step to store a list entities into ArangoDB."""
    payload_obj: NodePayloadList = step_input.previous_step_content

    if not payload_obj:
        log.warning("store_graph_step received no payloads to store. Skipping.")
        return StepOutput(
            step_name=step_name,
            content={"success": False},
            success=True,
        )

    sql_handler = InternalDB()
    handler = GraphStorageHandler(sql_handler)

    try:
        handler.store_subgraph(step_input.additional_data("canonical_name"))
        log.info("Successfully stored entities in the graph.")
    except Exception as e:
        log.error(f"An error occurred during graph storage: {e}", exc_info=True)
        handler.close()  # ensure client is closed on error
        return StepOutput(
            step_name=step_name,
            success=False,
            error=str(e),
        )
    finally:
        handler.close()

    return StepOutput(
        step_name=step_name,
        content={"success": True},
        success=True,
    )
