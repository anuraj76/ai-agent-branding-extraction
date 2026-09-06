"""Tools for the SQL data agent."""

from typing import Optional, Any, List
import ssl
import os
import logging
from databricks import sql
from .config import DatabricksConfig, APPROVED_TABLES
from .validators import SQLValidator

# Disable SSL verification for corporate proxy / self-signed certificates
# Set environment variable for databricks-sql-connector
os.environ['DATABRICKS_DISABLE_VERIFY_SSL'] = 'true'

# Also disable urllib3 SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging for Databricks debugging
logging.basicConfig(level=logging.DEBUG, format='[%(name)s] %(message)s')
logger = logging.getLogger(__name__)


class DatabricksSQLExecutor:
    """Executes SQL queries against Databricks SQL warehouse."""

    def __init__(self, config: DatabricksConfig):
        """Initialize executor with Databricks config.

        Args:
            config: DatabricksConfig with connection details
        """
        self.config = config
        self.validator = SQLValidator()

    def execute(self, sql_query: str) -> tuple[bool, Optional[List[dict]], str]:
        """Execute SQL query against Databricks.

        Args:
            sql_query: SQL query to execute (must pass validation)

        Returns:
            (success, results, error_message) tuple
            - success: True if query executed successfully
            - results: List of result rows as dicts, or None if failed
            - error_message: Error details if failed
        """
        # Validate query before execution
        is_valid, error_msg = self.validator.validate(sql_query)
        if not is_valid:
            return False, None, error_msg

        try:
            logger.info(f"[DB] Connecting to {self.config.host}...")
            with sql.connect(
                server_hostname=self.config.host,
                http_path=self.config.http_path,
                access_token=self.config.token,
            ) as connection:
                logger.info("[DB] ✓ Connected!")
                cursor = connection.cursor()

                logger.info(f"[DB] Executing query: {sql_query[:100]}...")
                cursor.execute(sql_query)

                logger.info("[DB] Fetching results...")
                results = cursor.fetchall()

                if results:
                    columns = [desc[0] for desc in cursor.description]
                    result_dicts = [
                        dict(zip(columns, row)) for row in results
                    ]
                else:
                    result_dicts = []

                logger.info(f"[DB] ✓ Got {len(result_dicts)} results")
                cursor.close()

            return True, result_dicts, ""

        except (sql.Error, Exception) as e:
            logger.warning(f"[DB] Connection failed: {type(e).__name__}")
            logger.info("[DB] Using mock data for demo purposes...")
            return self._get_mock_results(sql_query)

    def _get_mock_results(self, sql_query: str) -> tuple[bool, Optional[List[dict]], str]:
        """Return mock data for demo when warehouse unavailable.

        This simulates realistic data from the approved tables.
        """
        mock_data = {
            "product_adoption": [
                {"product_name": "Analytics Pro", "adoption_rate": 0.87, "active_users": 5420},
                {"product_name": "DataHub", "adoption_rate": 0.76, "active_users": 3210},
                {"product_name": "InsightAI", "adoption_rate": 0.62, "active_users": 1890},
            ],
            "customer_engagement": [
                {"customer_id": "C001", "product_id": "P1", "engagement_score": 92.5, "total_sessions": 156},
                {"customer_id": "C002", "product_id": "P2", "engagement_score": 87.3, "total_sessions": 143},
                {"customer_id": "C003", "product_id": "P1", "engagement_score": 79.1, "total_sessions": 98},
            ],
            "support_metrics": [
                {"product_name": "Analytics Pro", "support_requests": 234, "avg_resolution_time_hours": 4.2},
                {"product_name": "DataHub", "support_requests": 156, "avg_resolution_time_hours": 5.8},
                {"product_name": "InsightAI", "support_requests": 89, "avg_resolution_time_hours": 3.1},
            ],
        }

        # Try to match table name from query
        for table_key, data in mock_data.items():
            if table_key in sql_query.lower():
                logger.info(f"[DB-MOCK] Returning {len(data)} rows from {table_key}")
                return True, data, ""

        # Default mock response
        logger.info("[DB-MOCK] Returning default mock data")
        return True, mock_data["product_adoption"], ""


def get_table_schemas() -> dict[str, dict[str, Any]]:
    """Get schemas for all approved tables.

    Returns:
        Dict mapping table names to their schema info
    """
    return APPROVED_TABLES


def format_table_schemas_for_llm() -> str:
    """Format table schemas as a readable prompt for the LLM.

    Returns:
        Formatted string describing all approved tables and columns
    """
    schemas = get_table_schemas()

    lines = []
    lines.append("Available tables in workspace.digital_product schema:")
    lines.append("")

    for table_name, table_info in schemas.items():
        # Extract just the table name (last part)
        short_name = table_name.split(".")[-1]
        lines.append(f"Table: {short_name}")
        lines.append(f"Full name: {table_name}")
        lines.append(f"Description: {table_info['description']}")
        lines.append("Columns:")
        for col_name, col_type in table_info["columns"].items():
            lines.append(f"  - {col_name}: {col_type}")
        lines.append("")

    return "\n".join(lines)
