"""Configuration for Databricks connectivity and multi-provider LLM setup."""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DatabricksConfig:
    """Databricks SQL connection configuration."""
    host: str
    http_path: str
    token: str
    catalog: str = "workspace"
    schema: str = "digital_product"

    @classmethod
    def from_env(cls) -> "DatabricksConfig":
        """Load config from environment variables."""
        host = os.getenv("DATABRICKS_HOST")
        http_path = os.getenv("DATABRICKS_HTTP_PATH")
        token = os.getenv("DATABRICKS_TOKEN")

        if not all([host, http_path, token]):
            raise ValueError(
                "Missing Databricks credentials. "
                "Set DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN"
            )

        return cls(
            host=host,
            http_path=http_path,
            token=token,
            catalog=os.getenv("DATABRICKS_CATALOG", "workspace"),
            schema=os.getenv("DATABRICKS_SCHEMA", "digital_product"),
        )


@dataclass
class LLMConfig:
    """LLM configuration (supports multiple providers: OpenAI, Gemini, Bedrock, etc)."""
    provider: str = "gemini"  # "openai", "gemini", "bedrock", etc
    model: str = "gemini-3.6-flash"
    temperature: float = 0.0
    max_tokens: int = 1024
    api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load config from environment variables."""
        provider = os.getenv("LLM_PROVIDER", "gemini")

        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "gemini":
            api_key = os.getenv("GOOGLE_API_KEY")
        else:
            api_key = None

        if not api_key:
            raise ValueError(
                f"Provider '{provider}' selected but required API key not set. "
                f"Set OPENAI_API_KEY or GOOGLE_API_KEY"
            )

        return cls(
            provider=provider,
            model=os.getenv("LLM_MODEL", "gemini-3.6-flash"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1024")),
            api_key=api_key,
        )


# Approved tables for SQL generation
APPROVED_TABLES = {
    "workspace.digital_product.product_adoption": {
        "description": "Product adoption metrics and trends",
        "columns": {
            "product_id": "str - Unique product identifier",
            "product_name": "str - Product name",
            "adoption_rate": "float - Adoption rate (0-1)",
            "active_users": "int - Number of active users",
            "date": "date - Metric date",
        },
    },
    "workspace.digital_product.customer_engagement": {
        "description": "Customer engagement metrics by product",
        "columns": {
            "customer_id": "str - Unique customer identifier",
            "product_id": "str - Unique product identifier",
            "engagement_score": "float - Engagement score (0-100)",
            "last_activity_date": "date - Last user activity date",
            "total_sessions": "int - Total sessions",
        },
    },
    "workspace.digital_product.support_metrics": {
        "description": "Support request metrics by product",
        "columns": {
            "product_id": "str - Unique product identifier",
            "support_requests": "int - Number of support requests",
            "avg_resolution_time_hours": "float - Average resolution time in hours",
            "critical_issues": "int - Number of critical issues",
            "date": "date - Metric date",
        },
    },
}
