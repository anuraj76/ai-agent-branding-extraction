"""SQL generation using LLM."""

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from .config import LLMConfig
from .tools import format_table_schemas_for_llm


class SQLGenerator:
    """Generates SQL queries from natural language questions using LLM."""

    SYSTEM_PROMPT = """You are an expert SQL analyst for a business intelligence system.

Your task is to convert natural language business questions into SQL queries.

IMPORTANT CONSTRAINTS:
1. Only use tables from workspace.digital_product schema
2. Only generate SELECT queries - NO INSERT, UPDATE, DELETE, DROP, ALTER, etc.
3. NEVER reference tables outside the approved list
4. NEVER make up column names - use only the columns listed in the schema
5. If the question cannot be answered with available data, say so clearly
6. Make queries efficient and readable
7. Include proper WHERE conditions and LIMIT clauses where appropriate

{table_schemas}

IMPORTANT:
- Always use the full table name (e.g., workspace.digital_product.product_adoption)
- Use clear column aliases for readability
- Order results by the most relevant column (e.g., highest adoption first)
"""

    def __init__(self, config: LLMConfig = None):
        """Initialize SQL generator with LLM config.

        Args:
            config: LLMConfig for model selection, or None for defaults
        """
        self.config = config or LLMConfig.from_env()

        # Initialize LLM based on provider
        if self.config.provider == "openai":
            self.llm = ChatOpenAI(
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                api_key=self.config.api_key,
            )
        elif self.config.provider == "gemini":
            self.llm = ChatGoogleGenerativeAI(
                model=self.config.model,
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_tokens,
                google_api_key=self.config.api_key,
            )
        else:
            raise ValueError(
                f"Unsupported LLM provider: {self.config.provider}. "
                "Supported: openai, gemini"
            )

    def generate(self, question: str) -> tuple[str, str]:
        """Generate SQL query from natural language question.

        Args:
            question: Natural language business question

        Returns:
            (sql_query, reasoning) tuple
            - sql_query: Generated SQL query
            - reasoning: LLM's explanation of the query
        """
        try:
            table_schemas_text = format_table_schemas_for_llm()

            system_prompt = self.SYSTEM_PROMPT.format(
                table_schemas=table_schemas_text
            )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content=(
                        f"Please generate a SQL query to answer this question:\n\n"
                        f"{question}\n\n"
                        f"Respond with:\n"
                        f"1. The SQL query in a code block\n"
                        f"2. Brief explanation of what the query does"
                    )
                ),
            ]

            response = self.llm.invoke(messages)

            # Handle different response formats (OpenAI returns string, Gemini returns list)
            if isinstance(response.content, list):
                response_text = "\n".join(str(item) for item in response.content)
            else:
                response_text = response.content

            # Extract SQL from response
            sql_query = self._extract_sql(response_text)

            return sql_query, response_text

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"[LLM] Generation failed: {type(e).__name__}. Using demo mode...")
            return self._get_demo_query(question)

    def _get_demo_query(self, question: str) -> tuple[str, str]:
        """Return a demo SQL query when LLM is unavailable (quota/API issues).

        This demonstrates the full agent flow without burning API credits.
        """
        demo_queries = {
            "adoption": (
                "SELECT product_name, adoption_rate, active_users FROM workspace.digital_product.product_adoption ORDER BY adoption_rate DESC LIMIT 10",
                "Query to find products with highest adoption rates and active user counts"
            ),
            "engagement": (
                "SELECT customer_id, product_id, engagement_score FROM workspace.digital_product.customer_engagement ORDER BY engagement_score DESC LIMIT 10",
                "Query to identify most engaged customers by product"
            ),
            "support": (
                "SELECT product_name, support_requests, avg_resolution_time_hours FROM workspace.digital_product.support_metrics ORDER BY support_requests DESC",
                "Query to analyze support demand and resolution times by product"
            ),
        }

        # Match question to demo query
        question_lower = question.lower()
        for key, (sql, reasoning) in demo_queries.items():
            if key in question_lower:
                return sql, reasoning

        # Default to adoption query
        return demo_queries["adoption"]

    @staticmethod
    def _extract_sql(response_text: str) -> str:
        """Extract SQL query from LLM response.

        Looks for SQL in markdown code blocks or as plain text.

        Args:
            response_text: Full LLM response

        Returns:
            Extracted SQL query
        """
        import re

        # Try to extract from markdown code block first
        sql_match = re.search(
            r"```(?:sql)?\s*\n(.*?)\n```",
            response_text,
            re.DOTALL | re.IGNORECASE,
        )

        if sql_match:
            return sql_match.group(1).strip()

        # If no code block, look for SELECT statement
        select_match = re.search(
            r"(SELECT\s+.*?)(?:\n\n|$)",
            response_text,
            re.DOTALL | re.IGNORECASE,
        )

        if select_match:
            return select_match.group(1).strip()

        # Fallback: return response as-is (might be error message)
        return response_text.strip()
