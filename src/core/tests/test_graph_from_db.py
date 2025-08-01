from xflow_graph.adapters.arango import ArangoAdapter
from xflow_graph.models import create_model_instance, generate_document_id
from xflow_graph.services.graph import GraphService

from core.clients.sqlite import get_connection


def main():
    conn = get_connection()  # connect to SQLite

    # Initialize Arango adapter and graph service
    adapter = ArangoAdapter.connect()
    service = GraphService(adapter)

    # Fetch all companies
    companies = conn.execute("SELECT id, name FROM companies ORDER BY name").fetchall()
    if not companies:
        print("No companies found in the database.")
        return

    for comp in companies:
        # Upsert company node
        comp_key = generate_document_id().replace("-", "")[:16]
        comp_id = f"OrganizationUnit/{comp_key}"
        comp_doc = create_model_instance(
            "OrganizationUnit",
            {"_key": comp_key, "name": comp["name"], "sub_type": "Company"},
        )
        service.upsert_node("OrganizationUnit", comp_doc)

        # Fetch product lines for this company
        sql = (
            "SELECT id, name, type, description, category "
            "FROM product_lines "
            "WHERE company_id = ? "
            "ORDER BY name"
        )
        rows = conn.execute(sql, (comp["id"],)).fetchall()
        if not rows:
            print(f"No product lines for company '{comp['name']}' (ID {comp['id']}).")
            continue

        node_ops = []
        edge_docs = []
        for r in rows:
            # Create product node
            prod_key = generate_document_id().replace("-", "")[:16]
            prod_id = f"DomainEntity/{prod_key}"
            node_doc = create_model_instance(
                "DomainEntity",
                {
                    "_key": prod_key,
                    "name": r["name"],
                    "sub_type": r["category"] or "",
                    "attributes": {"description": r["description"] or ""},
                },
            )
            node_ops.append({"collection": "DomainEntity", "doc": node_doc})

            # Create PartOfProduct edge
            edge_data = create_model_instance(
                "PartOfProduct",
                {"source_id": comp_id, "target_id": prod_id},
                is_edge=True,
            )
            edge_fmt = {
                **edge_data.model_dump(),
                "_from": edge_data.source_id,
                "_to": edge_data.target_id,
            }
            edge_docs.append(edge_fmt)

        # Batch upsert nodes and link edges for this company
        service.batch_upsert_nodes(node_ops, use_transaction=False)
        service.link_edges("PartOfProduct", edge_docs)

        print(f"Processed company '{comp['name']}' with {len(rows)} product lines.")


if __name__ == "__main__":
    main()
