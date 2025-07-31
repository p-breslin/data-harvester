import json

from xflow_graph.adapters.arango import ArangoAdapter
from xflow_graph.mappings.schema import load_mapping_from_file
from xflow_graph.models import create_model_instance, generate_document_id

from core.utils.paths import CONFIG_DIR, DATA_DIR

# Load data
path = DATA_DIR / "workflow_outputs/2025-07-30_15-22-24/extract_output.json"
with open(path, "r") as file:
    data = json.load(file)

# load_mapping_from_file loads mapping config (currently unused)
mapping = load_mapping_from_file(CONFIG_DIR / "mapping.yml")

# ArangoAdapter handles DB connection and inserts
adapter = ArangoAdapter.connect()

# Create collections
adapter.create_collection_if_missing("OrganizationUnit")  # company node
adapter.create_collection_if_missing("DomainEntity")  # product node
adapter.create_collection_if_missing("PartOfProduct", edge=True)  # company -> product

# Generate a safe _key for the company (generate_document_id() gives a UUID)
# .replace("-", "")[:16] trims it to a safe _key format (Arango doesn’t allow - in _key)
company_key = generate_document_id().replace("-", "")[:16]
company_id = f"OrganizationUnit/{company_key}"  # company_id becomes the full Arango _id

# create_model_instance turns raw data into validated graph node/edge models
company = create_model_instance(
    "OrganizationUnit",
    {
        "_key": company_key,
        "name": data["company_name"],
        "sub_type": "Company",
    },
)
adapter.insert_nodes("OrganizationUnit", [company.model_dump()])  # inserts into Arango

# Create Product Nodes and Edges
offerings = []
edges = []

# Loop over each product/service in the input data
for item in data["product_lines"]:
    # Generate unique ID for each product/service
    offering_key = generate_document_id().replace("-", "")[:16]
    offering_id = f"DomainEntity/{offering_key}"

    # Build a DomainEntity node (representing a product or service)
    offering = create_model_instance(
        "DomainEntity",
        {
            "_key": offering_key,
            "name": item["name"],
            "sub_type": item["category"],
            "attributes": {"description": item["description"]},
        },
    )
    offerings.append(offering.model_dump())

    # Create an edge model from company -> product using the PartOfProduct edge type
    edge = create_model_instance(
        "PartOfProduct",
        {
            "source_id": company_id,
            "target_id": offering_id,
        },
        is_edge=True,
    )

    # Prepare the ArangoDB-compatible edge format with _from and _to
    edge_doc = {**edge.model_dump(), "_from": edge.source_id, "_to": edge.target_id}
    edges.append(edge_doc)

# Bulk insert - inserts all product nodes and all edges into the DB
adapter.insert_nodes("DomainEntity", offerings)
adapter.insert_edges("PartOfProduct", edges)

"""    
Field       Purpose
-----       -------------------------------------------
_key        Arango's unique document key (local, short)
id          Alias for _key in the Pydantic model
_id         Computed as CollectionName/_key in Arango
source_id   Pydantic input for edge's source
_from       Required Arango field for edge

"""