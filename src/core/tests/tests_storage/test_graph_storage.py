import logging
import sys

from .test_graph_handler import GraphStorageHandler
from .test_sql_handler import InternalDB

log = logging.getLogger(__name__)


def main(company_name: str):
    db = InternalDB()
    handler = GraphStorageHandler(db)

    try:
        # Export the subgraph for this company
        ctx = handler.store_subgraph(company_name)
        log.info(
            "Stored subgraph for %r: ArangoDB key = %r",
            company_name,
            ctx.key,
        )

    except Exception as e:
        log.error("Failed to store subgraph: %s", e)
        sys.exit(1)

    finally:
        handler.close()  # clean up


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    company = sys.argv[1] if len(sys.argv) > 1 else "Apple Inc."
    main(company)
