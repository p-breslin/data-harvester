import argparse
import sqlite3
from pathlib import Path

from core.utils.paths import DATA_DIR


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def list_companies(conn: sqlite3.Connection):
    cursor = conn.execute("SELECT id, name, created_at FROM companies ORDER BY name")
    companies = cursor.fetchall()
    if not companies:
        print("No companies found.")
        return

    # Print header
    print(f"{'ID':>3}  {'Name':<30}  {'Created At'}")
    print("---  " + "-" * 30 + "  " + "-" * 19)
    for c in companies:
        print(f"{c['id']:>3}  {c['name']:<30}  {c['created_at']}")


def list_product_lines(conn: sqlite3.Connection):
    sql = """
    SELECT pl.id, c.name AS company, pl.name, pl.type, pl.category, pl.created_at
    FROM product_lines pl
    JOIN companies c ON pl.company_id = c.id
    ORDER BY c.name, pl.name
    """
    cursor = conn.execute(sql)
    rows = cursor.fetchall()
    if not rows:
        print("No product lines found.")
        return

    # Print header
    print(
        f"{'ID':>3}  {'Company':<20}  {'Name':<25}  {'Type':<15}  {'Category':<15}  {'Created At'}"
    )
    print(
        "---  "
        + "-" * 20
        + "  "
        + "-" * 25
        + "  "
        + "-" * 15
        + "  "
        + "-" * 15
        + "  "
        + "-" * 19
    )
    for r in rows:
        print(
            f"{r['id']:>3}  {r['company']:<20}  {r['name']:<25}  {r['type'] or 'N/A':<15}  "
            f"{r['category'] or 'N/A':<15}  {r['created_at']}"
        )


def show_products_for_company(conn: sqlite3.Connection, company_identifier: str):
    # Try numeric id first, otherwise treat as name
    if company_identifier.isdigit():
        cond = ("c.id = ?", (int(company_identifier),))
    else:
        cond = ("c.name = ?", (company_identifier,))
    sql = f"""
    SELECT pl.id, pl.name, pl.type, pl.description, pl.category, pl.created_at
    FROM product_lines pl
    JOIN companies c ON pl.company_id = c.id
    WHERE {cond[0]}
    ORDER BY pl.name
    """
    cursor = conn.execute(sql, cond[1])
    rows = cursor.fetchall()
    if not rows:
        print(f"No product lines found for company '{company_identifier}'.")
        return
    print(f"Product lines for '{company_identifier}':")
    for r in rows:
        print(
            f"  • [{r['id']}] {r['name']} ({r['type'] or 'N/A'} / {r['category'] or 'N/A'})"
        )
        if r["description"]:
            print(f"      {r['description']}")


def main():
    parser = argparse.ArgumentParser(
        description="Query the company_data SQLite database"
    )
    default_db = DATA_DIR / "rag" / "company_data.db"
    parser.add_argument(
        "--db-path",
        "-d",
        type=Path,
        default=default_db,
        help=f"Path to the SQLite DB (default: {default_db})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-companies", help="List all companies")
    sub.add_parser("list-product-lines", help="List all product lines across companies")
    sp = sub.add_parser(
        "company-products",
        help="Show product lines for a given company (by ID or name)",
    )
    sp.add_argument("company", help="Company ID (integer) or exact company name")

    args = parser.parse_args()
    conn = get_connection(args.db_path)

    if args.command == "list-companies":
        list_companies(conn)
    elif args.command == "list-product-lines":
        list_product_lines(conn)
    elif args.command == "company-products":
        show_products_for_company(conn, args.company)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
