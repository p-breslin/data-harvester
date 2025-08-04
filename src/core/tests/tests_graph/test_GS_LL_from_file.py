import json

from xflow_graph.adapters.arango import ArangoAdapter
from xflow_graph.models import create_model_instance, generate_document_id
from xflow_graph.services.graph import GraphService

from core.utils.paths import DATA_DIR


def main():
    # Load data
    path = DATA_DIR / "workflow_outputs/2025-07-30_15-22-24/extract_output.json"
    with open(path, "r") as file:
        data = json.load(file)

    # Initialize Arango adapter and graph service API
    adapter = ArangoAdapter.connect()
    service = GraphService(adapter)

    # Upsert the company node
    company_key = generate_document_id().replace("-", "")[:16]
    company_id = f"OrganizationUnit/{company_key}"
    company_doc = create_model_instance(
        "OrganizationUnit",
        {
            "_key": company_key,
            "name": data["company_name"],
            "sub_type": "Company",
        },
    )
    # GraphService.upsert_node()
    service.upsert_node("OrganizationUnit", company_doc)

    # Prepare all product nodes + the PartOfProduct edges
    node_ops = []
    edge_docs = []

    for item in data["product_lines"]:
        # generate a unique key + Arango _id
        offering_key = generate_document_id().replace("-", "")[:16]
        offering_id = f"DomainEntity/{offering_key}"

        # a) node payload
        node_doc = create_model_instance(
            "DomainEntity",
            {
                "_key": offering_key,
                "name": item["name"],
                "sub_type": item["category"],
                "attributes": {"description": item["description"]},
            },
        )
        node_ops.append(
            {
                "collection": "DomainEntity",
                "doc": node_doc,
            }
        )

        # b) edge payload (validated via Pydantic)
        edge_data = create_model_instance(
            "PartOfProduct",
            {
                "source_id": company_id,
                "target_id": offering_id,
            },
            is_edge=True,
        )
        # convert to Arango’s required _from/_to fields
        edge_fmt = {
            **edge_data.model_dump(),
            "_from": edge_data.source_id,
            "_to": edge_data.target_id,
        }
        edge_docs.append(edge_fmt)

    # Batch-upsert all product nodes - GraphService.batch_upsert_nodes()
    service.batch_upsert_nodes(node_ops, use_transaction=False)

    # Bulk link all PartOfProduct edges - GraphService.link_edges()
    service.link_edges("PartOfProduct", edge_docs)


if __name__ == "__main__":
    main()
