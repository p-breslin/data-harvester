"""
CLI tool to manage (create/delete) ArangoDB databases
"""

import argparse
import logging
import os

from arango import ArangoClient
from dotenv import load_dotenv

from core.utils.logger import setup_logging

load_dotenv()
setup_logging()
log = logging.getLogger(__name__)


class ArangoManager:
    """Encapsulates ArangoDB system-level operations."""

    def __init__(self, host=None, user=None, password=None):
        host = host or os.getenv("ARANGO_HOST")
        user = user or os.getenv("ARANGO_USER", "root")
        password = password or os.getenv("ARANGO_PASSWORD")
        try:
            client = ArangoClient(hosts=host)
            self.sys_db = client.db("_system", username=user, password=password)
        except Exception as e:
            log.error(f"ArangoDB connection/auth failure: {e}")
            raise

    def create(self, db_name: str, reset: bool = False):
        """
        Create a database. If reset=True and the DB exists, delete it first.
        """
        if self.sys_db.has_database(db_name):
            if reset:
                self.sys_db.delete_database(db_name)
                log.info(f"Deleted existing database '{db_name}'")
            else:
                log.warning(
                    f"Database '{db_name}' already exists. Use --reset to recreate."
                )
                return
        self.sys_db.create_database(db_name)
        log.info(f"Created database '{db_name}'")

    def delete(self, db_name: str):
        """Delete a database if it exists."""
        if self.sys_db.has_database(db_name):
            self.sys_db.delete_database(db_name)
            log.info(f"Deleted database '{db_name}'")
        else:
            log.warning(f"Database '{db_name}' does not exist.")


def parse_args() -> argparse.Namespace:
    """Parses CLI arguments and returns a namespace."""
    parser = argparse.ArgumentParser(description="Manage ArangoDB databases via CLI")
    parser.add_argument(
        "-H",
        "--host",
        help="ArangoDB host URL (env: ARANGO_HOST)",
    )
    parser.add_argument(
        "-u",
        "--user",
        help="ArangoDB user (env: ARANGO_USER)",
        default=os.getenv("ARANGO_USER", "root"),
    )
    parser.add_argument(
        "-p",
        "--password",
        help="ArangoDB password (env: ARANGO_PASSWORD)",
        default=os.getenv("ARANGO_PASSWORD"),
    )
    parser.add_argument(
        "-d",
        "--db-name",
        help="Target database name (env: ARANGO_DB)",
        default=os.getenv("ARANGO_DB"),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a database")
    create.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing DB before creation",
    )

    sub.add_parser("delete", help="Delete a database")

    return parser.parse_args()


def main():
    args = parse_args()
    manager = ArangoManager(host=args.host, user=args.user, password=args.password)

    if args.command == "create":
        manager.create(args.db_name, reset=args.reset)
    elif args.command == "delete":
        manager.delete(args.db_name)


if __name__ == "__main__":
    main()
