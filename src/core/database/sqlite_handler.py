from typing import Any, Dict

from core.database.sqlite_db import CompanyDataDB


class SqliteStorageHandler:
    def __init__(self, db_path: str = None):
        """Initializes the SQLite storage handler using the specified database path.

        This constructor wraps access to a `CompanyDataDB` instance that provides methods for inserting and updating structured company and product line data.

        Args:
            db_path (str, optional): Path to the SQLite database file. If not provided,the default path from `CompanyDataDB` will be used.
        """
        self.db = CompanyDataDB(db_path) if db_path else CompanyDataDB()

    def store_product_lines(self, product_list: Dict[str, Any]) -> int:
        """Stores a list of product lines in the SQLite database.

        Ensures the company exists in the `companies` table, then inserts or replaces each product line into the `product_lines` table.

        Args:
            product_list (Dict[str, Any]): A dictionary containing:
                - 'company_name': str
                - 'product_lines': List of dicts with keys 'name', 'type', 'description', 'category'

        Returns:
            int: The number of product lines stored.
        """
        self.db.insert_company(product_list["company_name"])  # Ensures company exists
        self.db.insert_product_lines(product_list)
        return len(product_list["product_lines"])

    def store_company_profile(self, profile: Dict[str, Any]) -> None:
        """Stores a structured company profile in the SQLite database.

        Associates the profile with an existing or newly created company entry, and inserts or updates the corresponding row in the `company_profiles` table.

        Args:
            profile (Dict[str, Any]): A dict representation of a CompanyProfile.
        """
        self.db.insert_company_profile(profile)
