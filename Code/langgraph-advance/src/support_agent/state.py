"""LangGraph state definition for the SQL data agent."""

from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class AgentState:
    """State for the SQL data agent workflow.

    This state flows through the LangGraph:
    1. question → analyze_question → understand intent
    2. sql_query → generate_sql → create SQL
    3. sql_query → validate_sql → ensure safety
    4. sql_result → execute_sql → run against Databricks
    5. sql_result → final_answer → business-friendly response
    """

    # Input: the user's natural language question
    question: str

    # Analysis phase: what tables/concepts are needed
    table_analysis: str = ""

    # SQL generation phase: the generated SQL query
    sql_query: str = ""

    # Validation phase: whether the SQL is safe
    is_valid: bool = False
    validation_error: str = ""

    # Execution phase: result from Databricks
    sql_result: Optional[list[dict[str, Any]]] = None
    sql_error: str = ""

    # Retry tracking
    retry_count: int = 0
    max_retries: int = 2

    # Final answer phase: business-friendly response
    final_answer: str = ""

    # Internal: table schemas available to LLM
    table_schemas: dict = field(default_factory=dict)

    def should_retry(self) -> bool:
        """Check if we should retry SQL generation."""
        return self.retry_count < self.max_retries and not self.is_valid

    def increment_retry(self) -> None:
        """Increment retry counter."""
        self.retry_count += 1
