import sqlite3
from pathlib import Path

from core.utils.paths import DATA_DIR

default_db = DATA_DIR / "rag" / "company_data.db"


def get_connection(db_path: Path = default_db) -> sqlite3.Connection:
    """Establish a connection to the SQLite database and configure row factory."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn
