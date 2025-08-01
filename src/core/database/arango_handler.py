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

    def _upsert_company_node(self, company_name: str) -> str:
        """Ensures the existence of an OrganizationUnit node for a given company.

        Fetches the company from the SQLite database and upserts it as an OrganizationUnit node in the ArangoDB graph with a generated key.

        Args:
            company_name (str): The name of the company to insert or update in ArangoDB.

        Returns:
            str: The full ArangoDB `_id` of the upserted OrganizationUnit node.
        """
        row = self.sqlite_conn.execute(
            """
            SELECT
            companies.id      AS company_id,
            companies.name    AS company_name,
            company_profiles.cik
            FROM companies
            LEFT JOIN company_profiles
            ON company_profiles.company_id = companies.id
            WHERE companies.name = ?
            """,
            (company_name,),
        ).fetchone()

        if not row:
            raise ValueError(f"Company '{company_name}' not found in SQLite")

        cik_key = row["cik"].lstrip("0") if row["cik"] else row["company_id"]
        comp_key = cik_key
        comp_id = f"OrganizationUnit/{comp_key}"

        comp_doc = create_model_instance(
            "OrganizationUnit",
            {
                "_key": comp_key,
                "name": row["company_name"],
                "sub_type": "Company",
            },
        )
        self.service.upsert_node("OrganizationUnit", comp_doc)
        return comp_id

    def store_company_profile(self, profile: Dict[str, Any]) -> None:
        """Stores company profile attributes on an OrganizationUnit node.

        Uses the company's CIK (stripped of leading zeros) as the node key, and attaches structured metadata in ArangoDB.

        Args:
            profile (Dict[str, Any]): A dict representation of a CompanyProfile object.
        """

        cik_key = profile["cik"].lstrip("0")  # CIK as stable key (strip leading zeros)

        # Build the full attribute set
        doc_body = {
            "_key": cik_key,
            "name": profile["company_name"],
            "sub_type": "Company",
            # profile fields:
            "ticker": profile.get("ticker"),
            "industry": profile.get("industry"),
            "location": profile.get("location"),
            "sic_code": profile.get("sic_code"),
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

    def store_product_lines(self, company_name: str) -> int:
        """Stores product lines as DomainEntity nodes and links them to the company.

        Reads product lines from SQLite for a given company, upserts each product line as a DomainEntity node in ArangoDB, and links it to the associated OrganizationUnit node with a PartOfProduct edge.

        Args:
            company_name (str): Name of company whose product lines should be stored.

        Returns:
            int: Number of product lines successfully processed and stored in ArangoDB.
        """
        comp_id = self._upsert_company_node(company_name)

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
