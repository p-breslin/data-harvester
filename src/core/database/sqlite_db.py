import sqlite3
from typing import Any, Dict

from core.utils.paths import DATA_DIR


class CompanyDataDB:
    def __init__(self):
        output_dir = DATA_DIR / "rag"
        output_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = output_dir / "company_data.db"
        self.init_database()

    def init_database(self):
        """Create database and tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            # Companies table (central reference)
            conn.execute("""  
                CREATE TABLE IF NOT EXISTS companies (  
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  
                    name TEXT UNIQUE NOT NULL,  
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  
                )  
            """)

            # Company profile table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    ticker TEXT,
                    cik TEXT,
                    industry TEXT,
                    location TEXT,
                    sic_code TEXT,
                    fiscal_year_end TEXT,
                    exchanges TEXT,  -- comma-separated list
                    shares_outstanding INTEGER,
                    public_float INTEGER,
                    revenue_value REAL,
                    revenue_period TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id),
                    UNIQUE(company_id)
                )
            """)

            # Product lines table
            conn.execute("""  
                CREATE TABLE IF NOT EXISTS product_lines (  
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  
                    company_id INTEGER NOT NULL,  
                    name TEXT NOT NULL,  
                    type TEXT CHECK(type IN ('product', 'service', 'product and service')),  
                    description TEXT,  
                    category TEXT,  
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  
                    FOREIGN KEY (company_id) REFERENCES companies(id),  
                    UNIQUE(company_id, name)  
                )  
            """)

            # Customers table
            # Competitors table
            # Suppliers table

            conn.commit()

    def insert_company(self, company_name: str) -> int:
        """Insert company and return company_id"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO companies (name) VALUES (?)", (company_name,)
            )
            conn.commit()

            # Get company_id
            cursor = conn.execute(
                "SELECT id FROM companies WHERE name = ?", (company_name,)
            )
            return cursor.fetchone()[0]

    def insert_company_profile(self, profile: Dict[str, Any]):
        """Insert or update CompanyProfile data"""
        company_name = profile["company_name"]
        company_id = self.insert_company(company_name)

        exchanges = profile.get("exchanges")
        if isinstance(exchanges, list):
            exchanges_str = ",".join(exchanges)
        else:
            exchanges_str = None

        revenue = profile.get("latest_revenue", {})
        revenue_value = revenue.get("numeric_value")
        revenue_period = revenue.get("period_end")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO profiles (
                    company_id,
                    ticker,
                    cik,
                    industry,
                    location,
                    sic_code,
                    fiscal_year_end,
                    exchanges,
                    shares_outstanding,
                    public_float,
                    revenue_value,
                    revenue_period
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    company_id,
                    profile.get("ticker"),
                    profile.get("cik"),
                    profile.get("industry"),
                    profile.get("location"),
                    profile.get("sic_code"),
                    profile.get("fiscal_year_end"),
                    exchanges_str,
                    profile.get("shares_outstanding"),
                    profile.get("public_float"),
                    revenue_value,
                    revenue_period,
                ),
            )
            conn.commit()

    def insert_product_lines(self, product_line_list: Dict[str, Any]):
        """Insert ProductLineList data into database"""
        company_name = product_line_list["company_name"]
        product_lines = product_line_list["product_lines"]

        company_id = self.insert_company(company_name)

        with sqlite3.connect(self.db_path) as conn:
            for pl in product_lines:
                conn.execute(
                    """  
                    INSERT OR REPLACE INTO product_lines   
                    (company_id, name, type, description, category)  
                    VALUES (?, ?, ?, ?, ?)  
                """,
                    (
                        company_id,
                        pl["name"],
                        pl.get("type"),
                        pl.get("description"),
                        pl.get("category"),
                    ),
                )
            conn.commit()
