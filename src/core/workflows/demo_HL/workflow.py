import asyncio
import logging
from datetime import datetime

from agno.storage.sqlite import SqliteStorage
from agno.workflow.v2 import Step, Workflow

from core.utils.helpers import load_yaml
from core.utils.logger import setup_logging
from core.utils.paths import DATA_DIR

from .agent_steps import (
    extract_step,
    profile_step,
    search_step,
    seed_step,
    transform_step,
)
from .storage_steps import store_graph_step, store_sql_step

# --- Set up ---------------------------------------------------------------------------

setup_logging()
log = logging.getLogger(__name__)

# Configuration file
cfg = load_yaml("product_line")

# Save path for workflow output
execution_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
output_path = DATA_DIR / "workflow_outputs" / execution_time
output_path.mkdir(parents=True, exist_ok=True)


# --- Workflow Execution ---------------------------------------------------------------


async def main():
    """Orchestrates the end-to-end product profiling Agno workflow for a target company.

    This function sets up and executes a multi-step workflow that:
      1. Generates a structured company profile from SEC and web search data.
      2. Transforms and stores the profile in both SQLite and ArangoDB.
      3. Discovers the company's public product lines via web search.
      4. Seeds each product line with representative URLs.
      5. Extracts structured product information from those URLs.
      6. Transforms and stores extracted product line data in both SQLite and ArangoDB.

    Workflow configuration is loaded from a YAML file, and runtime outputs are persisted to a timestamped directory for later inspection.
    """
    rt = cfg["runtime"]
    product_workflow = Workflow(
        name=rt["name"],
        description=rt["description"],
        storage=SqliteStorage(
            table_name=rt["table_name"],
            db_file=rt["db_file"],
            mode="workflow_v2",
        ),
        steps=[
            # Company Profile Sub-flow
            Step(name=rt["profile"], executor=profile_step),
            Step(name=rt["transform"], executor=transform_step),
            Step(name=rt["sql_db"], executor=store_sql_step(rt["sql_db"])),
            Step(name=rt["graph_db"], executor=store_graph_step(rt["graph_db"])),
            # Product Line Sub-flow
            Step(name=rt["search"], executor=search_step),
            Step(name=rt["seed"], executor=seed_step),
            Step(name=rt["extract"], executor=extract_step),
            Step(name=rt["transform"], executor=transform_step),
            Step(name=rt["sql_db"], executor=store_sql_step(rt["sql_db"])),
            Step(name=rt["graph_db"], executor=store_graph_step(rt["graph_db"])),
        ],
    )
    trigger = {"company": rt["company"], "N": rt["N_product_lines"]}
    workflow_success = True

    # Run the workflow and iterate over the stream
    async for event in await product_workflow.arun(
        message=trigger,
        additional_data={
            "output_path": output_path,
            "company_name": rt["company"],
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
