import os
from typing import Any, Dict

from xflow_graph.adapters.arango import ArangoAdapter
from xflow_graph.models import create_model_instance, generate_document_id
from xflow_graph.services.graph import GraphService

from core.clients.arango import ArangoManager
from core.clients.sqlite import get_connection
from core.utils.helpers import safe_date


class ArangoStorageHandler:
    def __init__(self, db_name: str = None):
        """Initializes the ArangoStorageHandler with access to both ArangoDB and SQLite.

        This constructor ensures that the target ArangoDB database exists, establishes a connection to the graph service for node and edge operations, and opens a SQLite connection to allow cross-database coordination.

        Args:
            db_name (str, optional): The name of the ArangoDB database to connect to. If not provided, it defaults to the value of the ARANGO_DB env variable.
        """
        self.manager = ArangoManager()
        self.db_name = db_name or os.getenv("ARANGO_DB")
        if not self.manager.exists(self.db_name):
            self.manager.create(self.db_name)
        self.adapter = ArangoAdapter.connect()
        self.service = GraphService(self.adapter)
        self.sqlite_conn = get_connection()

    def store_company_profile(self, profile: Dict[str, Any], key: str) -> None:
        """Stores company profile attributes on an OrganizationUnit.

        Args:
            profile (Dict[str, Any]): A dict representation of a CompanyProfile object
            key (str): The pre-generated UUID to use as the document _key.
        """

        # Build the full attribute set
        doc_body = {
            "_key": key,
            "name": profile["company_name"],
            "sub_type": "Company",
            # external identifiers
            "external_ids": {
                "cik": profile.get("cik"),
                "ticker": profile.get("ticker"),
                "sic_code": profile.get("sic_code"),
            },
            # profile fields
            "website": profile.get("website"),
            "industry": profile.get("industry"),
            "location": profile.get("location"),
            "fiscal_year_end": safe_date(profile.get("fiscal_year_end")),
            "exchanges": profile.get("exchanges") or [],
            "shares_outstanding": profile.get("shares_outstanding"),
            "public_float": profile.get("public_float"),
        }

        # Latest revenue as a nested sub‐object
        if profile.get("latest_revenue"):
            lr = profile["latest_revenue"]
            doc_body["latest_revenue"] = {
                "value": lr["numeric_value"],
                "period": safe_date(lr["period_end"]),
            }

        comp_doc = create_model_instance("OrganizationUnit", doc_body)
        self.service.upsert_node("OrganizationUnit", comp_doc)

    def store_product_lines(self, company_name: str, key: str) -> int:
        """Stores product lines as DomainEntity nodes and links them to the company.

        Reads product lines from SQLite for a given company, upserts each product line as a DomainEntity node in ArangoDB, and links it to the associated OrganizationUnit node with a PartOfProduct edge.

        Args:
            company_name (str): Name of company whose product lines should be stored.
            key (str): The UUID key of the parent OrganizationUnit node.


        Returns:
            int: Number of product lines successfully processed and stored in ArangoDB.
        """

        comp_id = f"OrganizationUnit/{key}"
        rows = self.sqlite_conn.execute(
            """
            SELECT product_lines.id, product_lines.name, product_lines.type,
                product_lines.description, product_lines.category
            FROM product_lines
            INNER JOIN companies ON product_lines.company_id = companies.id
            WHERE companies.name = ?
            """,
            (company_name,),
        ).fetchall()
        if not rows:
            return 0

        node_ops, edge_docs = [], []
        for r in rows:
            prod_key = generate_document_id().replace("-", "")[:16]
            prod_id = f"DomainEntity/{prod_key}"
            node_ops.append(
                {
                    "collection": "DomainEntity",
                    "doc": create_model_instance(
                        "DomainEntity",
                        {
                            "_key": prod_key,
                            "name": r["name"],
                            "sub_type": r["category"] or "",
                            "attributes": {"description": r["description"] or ""},
                        },
                    ),
                }
            )
            edge_docs.append({"_from": comp_id, "_to": prod_id})

        self.service.batch_upsert_nodes(node_ops, use_transaction=False)
        self.service.link_edges("PartOfProduct", edge_docs)
        return len(rows)
