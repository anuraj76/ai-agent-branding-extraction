"""SQL validation for safety and security."""

import re
from typing import Optional, Set
from .config import APPROVED_TABLES


class SQLValidator:
    """Validates SQL queries for safety before execution."""

    # Dangerous SQL keywords that should never appear
    DANGEROUS_KEYWORDS = {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "MERGE",
        "EXEC",
        "EXECUTE",
        "SCRIPT",
    }

    # SQL keywords that indicate multiple statements
    STATEMENT_SEPARATORS = {";"}

    def __init__(self, approved_tables: Optional[dict] = None):
        """Initialize validator with approved tables.

        Args:
            approved_tables: Dict of approved table names from config
        """
        self.approved_tables = approved_tables or APPROVED_TABLES
        self.approved_table_names = set(self.approved_tables.keys())

    def validate(self, sql_query: str) -> tuple[bool, str]:
        """Validate SQL query for safety.

        Returns:
            (is_valid, error_message) tuple
        """
        if not sql_query or not sql_query.strip():
            return False, "SQL query is empty"

        # Check for dangerous keywords
        error = self._check_dangerous_keywords(sql_query)
        if error:
            return False, error

        # Check for multiple statements
        error = self._check_multiple_statements(sql_query)
        if error:
            return False, error

        # Check for unapproved tables
        error = self._check_table_access(sql_query)
        if error:
            return False, error

        # Ensure it's a SELECT query
        error = self._check_select_only(sql_query)
        if error:
            return False, error

        return True, ""

    def _check_dangerous_keywords(self, sql_query: str) -> Optional[str]:
        """Check for dangerous SQL keywords."""
        query_upper = sql_query.upper()
        for keyword in self.DANGEROUS_KEYWORDS:
            if re.search(rf"\b{keyword}\b", query_upper):
                return f"Query contains dangerous keyword: {keyword}"
        return None

    def _check_multiple_statements(self, sql_query: str) -> Optional[str]:
        """Check for multiple SQL statements."""
        # Count semicolons (excluding those in comments)
        # Simple check: if there's a semicolon followed by non-whitespace, it's multiple statements
        parts = sql_query.split(";")
        if len(parts) > 2:  # More than one semicolon
            return "Query contains multiple statements (semicolon detected)"
        if len(parts) == 2 and parts[1].strip():  # Semicolon with content after it
            return "Query contains multiple statements"
        return None

    def _check_table_access(self, sql_query: str) -> Optional[str]:
        """Check that query only accesses approved tables."""
        query_upper = sql_query.upper()

        # Extract table names from FROM and JOIN clauses
        from_pattern = r"FROM\s+(\S+)"
        join_pattern = r"JOIN\s+(\S+)"

        tables_in_query = set()

        for match in re.finditer(from_pattern, query_upper):
            table_name = match.group(1).strip()
            # Clean up table name (remove aliases)
            table_name = re.sub(r"\s+AS\s+\w+", "", table_name, flags=re.IGNORECASE)
            table_name = re.split(r"\s+", table_name)[0]  # Take first part if multiple
            tables_in_query.add(table_name)

        for match in re.finditer(join_pattern, query_upper):
            table_name = match.group(1).strip()
            table_name = re.sub(r"\s+AS\s+\w+", "", table_name, flags=re.IGNORECASE)
            table_name = re.split(r"\s+", table_name)[0]
            tables_in_query.add(table_name)

        # Check each table is approved
        for table in tables_in_query:
            # Normalize table name to lowercase for comparison
            table_normalized = table.lower()

            # Check if it's in approved tables
            is_approved = any(
                approved.lower() == table_normalized
                for approved in self.approved_table_names
            )

            if not is_approved:
                return f"Query references unapproved table: {table}"

        return None

    def _check_select_only(self, sql_query: str) -> Optional[str]:
        """Ensure query starts with SELECT."""
        query_stripped = sql_query.strip()
        if not query_stripped.upper().startswith("SELECT"):
            return "Query must be a SELECT statement"
        return None
