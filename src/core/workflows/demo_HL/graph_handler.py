import json
import logging
import os
from typing import Any, Dict, List, Set

from dotenv import load_dotenv
from xflow_graph import GraphClient
from xflow_graph.sdk.business_objects import Context
from xflow_graph.services.graph import GraphService

from .sql_handler import InternalDB

load_dotenv()
log = logging.getLogger(__name__)


class GraphStorageHandler:
    def __init__(self, db: InternalDB):
        self.db = db
        self.client = GraphClient(
            host="localhost",
            port=8529,
            database=os.getenv("ARANGO_DB"),
            username=os.getenv("ARANGO_USERNAME"),
            password=os.getenv("ARANGO_PASSWORD"),
        )
        self.ctx_mgr = self.client.manager().contexts()
        self._service = GraphService(self.client.adapter)

    def store_subgraph(self, lookup_key: str) -> Context:
        """
        1) Find the root node by its lookup_key in the SQL database.
        2) BFS-traverse all connected edges in SQL.
        3) Upsert each node into Arango (using the lookup_key as the Arango _key).
        4) Bulk-link all edges.
        """
        conn = self.db._get_connection()

        # Step 1: load root by lookup_key
        root_row = conn.execute(
            "SELECT id, node_type, sub_type, lookup_key, data FROM nodes WHERE lookup_key = ?",
            (lookup_key,),
        ).fetchone()
        if not root_row:
            raise ValueError(f"No root node found for lookup_key={lookup_key!r}")

        root = dict(root_row)
        root["data"] = json.loads(root["data"])

        # Step 2: BFS to collect subgraph
        to_visit: List[int] = [root["id"]]
        visited: Set[int] = set()
        nodes: Dict[int, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        while to_visit:
            nid = to_visit.pop(0)
            if nid in visited:
                continue
            visited.add(nid)

            # fetch node once
            if nid not in nodes:
                row = conn.execute("SELECT * FROM nodes WHERE id=?", (nid,)).fetchone()
                rec = dict(row)
                rec["data"] = json.loads(rec["data"])
                nodes[nid] = rec

            # fetch connected edges
            for e in conn.execute(
                "SELECT * FROM edges WHERE from_id=? OR to_id=?", (nid, nid)
            ).fetchall():
                ed = dict(e)
                edges.append(ed)
                other = ed["to_id"] if ed["from_id"] == nid else ed["from_id"]
                if other not in visited:
                    to_visit.append(other)

        # Step 3: upsert nodes
        sql_to_ctx: Dict[int, Dict[str, Any]] = {}
        for rec in nodes.values():
            nt = rec["node_type"]  # e.g. "OrganizationUnit"
            st = rec["sub_type"]  # e.g. "Company"
            name = rec["lookup_key"]  # used as the Arango key/name
            attrs = rec["data"]  # all other properties

            # Try to fetch existing context
            doc_id = f"{nt}/{name}"  # node_type / lookup_key
            try:
                existing = self.ctx_mgr.get(doc_id)
            except Exception:
                existing = None

            if existing:
                # update its attributes (preserves created_at, etc.)
                self.ctx_mgr.update(
                    context_key=existing.key,
                    name=name,
                    attributes=attrs,
                )
                ctx = existing
            else:
                # create new
                ctx = self.ctx_mgr.create(
                    node_type=nt,
                    name=name,
                    sub_type=st,
                    attributes=attrs,
                )

            sql_to_ctx[rec["id"]] = {
                "ctx": ctx,
                "key": ctx.key,
                "collection": nt,
            }

        # Step 4: bulk-link edges
        links_by_rel: Dict[str, List[Dict[str, str]]] = {}

        for ed in edges:
            fctx = sql_to_ctx.get(ed["from_id"])
            tctx = sql_to_ctx.get(ed["to_id"])
            if not fctx or not tctx:
                continue

            from_id = f"{fctx['collection']}/{fctx['key']}"
            to_id = f"{tctx['collection']}/{tctx['key']}"
            rel_type = ed["edge_type"]

            links_by_rel.setdefault(rel_type, []).append(
                {
                    "_from": from_id,
                    "_to": to_id,
                }
            )

        # Deduplicate and then call batch_link_edges
        for rel_type, raw_edges in links_by_rel.items():
            seen: set[tuple[str, str]] = set()
            unique_edges: list[Dict[str, str]] = []

            for edge in raw_edges:
                key = (edge["_from"], edge["_to"])
                if key not in seen:
                    seen.add(key)
                    unique_edges.append(edge)

            # now link this one batch of unique edges
            self._service.batch_link_edges(
                [{"collection": rel_type, "edges": unique_edges}]
            )

        # Return the root Context object
        return sql_to_ctx[root["id"]]["ctx"]

    def close(self):
        self.client.close()
