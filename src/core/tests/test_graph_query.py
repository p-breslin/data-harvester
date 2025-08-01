"""
Demonstrates graph-driven queries with GraphService:
  1. Fetch a company node using query_by_key
  2. Discover its products via PartOfProduct edges
  3. Trace a shortest path from a product back to its company
"""

import json
from typing import Any, Dict, List, Optional

from xflow_graph.adapters.arango import ArangoAdapter
from xflow_graph.models.exceptions import GraphOperationError, GraphValidationError
from xflow_graph.services.graph import GraphService


def get_first_node(
    service: GraphService, adapter: ArangoAdapter, collection: str
) -> Optional[Dict[str, Any]]:
    """Find and return the first node in a collection using GraphService."""
    query = f"FOR d IN {collection} LIMIT 1 RETURN d._key"
    try:
        results = adapter.run_query(query)
        if not results:
            return None

        first_key = results[0]
        return service.query_by_key(collection, first_key)

    except Exception as e:
        print(f"Failed to get first node from {collection}: {e}")
        return None


def get_linked_nodes(
    adapter: ArangoAdapter,
    from_id: str,
    edge_collection: str,
    target_collection: str,
) -> List[Dict[str, Any]]:
    """Return all nodes in `target_collection` that are linked
    from `from_id` via edges in `edge_collection`.
    """
    aql = f"""
      FOR e IN {edge_collection}
          FILTER e._from == @from_id
          FOR t IN {target_collection}
              FILTER t._id == e._to
              RETURN t
    """
    return adapter.run_query(aql, {"from_id": from_id})


def main():
    # Initialize
    adapter = ArangoAdapter.connect()
    service = GraphService(adapter)

    # 1) Fetch a company using query_by_key
    print("\nFetching an example company node...")
    company = get_first_node(service, adapter, "OrganizationUnit")
    if not company:
        print("No companies found in the graph.")
        return

    company_id = company["_id"]
    print(f"Found company: {company.get('name', '(unnamed)')} ({company['_id']})")
    print("\nCompany data:")
    for k, v in company.items():
        print(f"  {k}: {v}")

    # 2) Discover its products
    print("\nDiscovering products linked via PartOfProduct...")

    # This query bypasses GraphService because there is no 'get_neighbors()' helper yet
    products = get_linked_nodes(adapter, company_id, "PartOfProduct", "DomainEntity")
    if not products:
        print("No products linked to this company.")
        return

    print(f"{len(products)} product(s) found:")
    for p in products:
        print(f"\nProduct: {p.get('name', '(unnamed)')}")
        print(f"  - ID: {p['_id']}")
        print(f"  - Key: {p['_key']}")
        print(f"  - Metadata: {p.get('metadata', 'N/A')}")
        print(f"  - Subtype: {p.get('sub_type', 'N/A')}")
        print(f"  - Attributes: {json.dumps(p.get('attributes', {}), indent=2)}")

    # 3) Trace a path from the first product back to the company
    first = products[0]
    print(
        f'\nExample path trace from product "{first.get("name", "(unnamed)")}" to company...'
    )
    try:
        path = service.find_path(
            start=first["_id"],
            end=company_id,
            edge_collections=["PartOfProduct"],
        )
        if not path:
            print("No path found.")
        else:
            print(f"Path with {len(path)} node(s):")
            for node in path:
                label = node.get("name") or node.get("id") or "(no name)"
                print(f"  - {node['_id']}: {label}")
    except (GraphValidationError, GraphOperationError) as e:
        print(f"Path query failed: {e}")
    print()


if __name__ == "__main__":
    main()
