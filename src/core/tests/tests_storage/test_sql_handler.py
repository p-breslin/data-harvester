import json
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional

from core.models import NodePayload
from core.utils.paths import DATA_DIR

logger = logging.getLogger(__name__)


class InternalDB:
    """Manages a SQLite DB for storing a generic graph structure (nodes + edges)."""

    def __init__(self, retries=3, initial_delay=0.1):
        self.db_path = DATA_DIR / "rag" / "company_data.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.retries = retries
        self.initial_delay = initial_delay
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Establishes a connection with production-ready settings."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=10,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """Creates the DB schema, including tables, robust triggers, and indexes."""
        with self._get_connection() as conn:
            cur = conn.cursor()

            # 1) Nodes table: updated_at defaults to CURRENT_TIMESTAMP
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_type  TEXT    NOT NULL,
                    sub_type   TEXT    NOT NULL,
                    lookup_key   TEXT    NOT NULL,
                    data         JSON    NOT NULL,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(node_type, lookup_key)
                );
            """)

            # 2) AFTER UPDATE trigger: non‐recursive, fires only when data changes
            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_nodes_after_update
                AFTER UPDATE ON nodes
                FOR EACH ROW
                WHEN OLD.data <> NEW.data
                BEGIN
                    UPDATE nodes
                       SET updated_at = CURRENT_TIMESTAMP
                     WHERE id = NEW.id;
                END;
            """)

            # 3) Edges table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    from_id     INTEGER NOT NULL,
                    to_id       INTEGER NOT NULL,
                    edge_type   TEXT    NOT NULL,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(from_id, to_id, edge_type),
                    FOREIGN KEY(from_id) REFERENCES nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY(to_id)   REFERENCES nodes(id) ON DELETE CASCADE
                );
            """)

            # 4) Indexes for lookups and incremental syncs
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_node_type_lookup_key ON nodes(node_type, lookup_key);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_nodes_created_at ON nodes(created_at);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_nodes_updated_at ON nodes(updated_at);"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_created_at ON edges(created_at);"
            )

    def _execute_with_retry(
        self, conn: sqlite3.Connection, sql: str, params: tuple = ()
    ):
        """Helper to retry a database execution on 'database is locked' errors."""
        delay = self.initial_delay
        for attempt in range(self.retries):
            try:
                return conn.execute(sql, params)
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < self.retries - 1:
                    logger.warning("Database locked, retrying in %.2fs…", delay)
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise

    def _get_node_id(
        self, conn: sqlite3.Connection, node_type: str, lookup_key: str
    ) -> Optional[int]:
        row = conn.execute(
            "SELECT id FROM nodes WHERE node_type = ? AND lookup_key = ?",
            (node_type, lookup_key),
        ).fetchone()
        return row["id"] if row else None

    def upsert_payloads(self, payloads: List[NodePayload]) -> None:
        """Upserts all nodes and edges using a two-pass strategy, merging node data if an node already exists."""
        with self._get_connection() as conn:
            try:
                # Pass 1: UPSERT all NODES
                for payload in payloads:
                    existing_row = conn.execute(
                        "SELECT data FROM nodes WHERE node_type = ? AND lookup_key = ?",
                        (payload.node_type, payload.lookup_key),
                    ).fetchone()

                    if existing_row:
                        existing_data = json.loads(existing_row["data"])
                        # Merge existing with incoming -> incoming wins on conflict
                        merged_data = {**existing_data, **payload.data}
                    else:
                        merged_data = payload.data

                    self._execute_with_retry(
                        conn,
                        """
                        INSERT INTO nodes (node_type, sub_type, lookup_key, data)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(node_type, lookup_key)
                        DO UPDATE SET data = excluded.data;
                        """,
                        (
                            payload.node_type,
                            payload.sub_type,
                            payload.lookup_key,
                            json.dumps(merged_data, sort_keys=True),
                        ),
                    )

                # Pass 2: INSERT all EDGES
                for payload in payloads:
                    if not payload.edges:
                        continue
                    from_id = self._get_node_id(
                        conn, payload.node_type, payload.lookup_key
                    )
                    if from_id is None:
                        continue

                    for edge in payload.edges:
                        to_id = self._get_node_id(
                            conn, edge.to_node_type, edge.to_lookup_key
                        )
                        if to_id:
                            self._execute_with_retry(
                                conn,
                                "INSERT OR IGNORE INTO edges (from_id, to_id, edge_type) VALUES (?, ?, ?)",
                                (from_id, to_id, edge.edge_type),
                            )

                conn.commit()

            except Exception as err:
                conn.rollback()
                logger.error("Transaction failed: %s. Rolled back.", err)
                raise

    def export_all_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Exports every node and edge in a generic JSON-friendly format."""
        with self._get_connection() as conn:
            nodes = []
            for row in conn.execute("SELECT * FROM nodes"):
                rec = dict(row)
                rec["data"] = json.loads(rec["data"])
                nodes.append(rec)

            edges = [dict(r) for r in conn.execute("SELECT * FROM edges")]
            return {"nodes": nodes, "edges": edges}

    def query_database(self) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieves all nodes and edges from the SQL database.

        Returns:
            A dict with two keys:
              - 'nodes': List of node dicts
              - 'edges': List of edge dicts
        """
        with self._get_connection() as conn:
            # Gather nodes
            nodes: List[Dict[str, Any]] = []
            for row in conn.execute("SELECT * FROM nodes ORDER BY id"):
                rec = dict(row)
                rec["data"] = json.loads(rec["data"])
                rec["created_at"] = str(rec["created_at"])
                rec["updated_at"] = str(rec["updated_at"])
                nodes.append(rec)

            # Gather edges
            edges: List[Dict[str, Any]] = []
            for row in conn.execute("SELECT * FROM edges ORDER BY from_id, to_id"):
                rec = dict(row)
                rec["created_at"] = str(rec["created_at"])
                edges.append(rec)

        return {
            "nodes": nodes,
            "edges": edges,
        }
