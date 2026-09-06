"""LangGraph SQL data agent orchestration."""

from langgraph.graph import StateGraph, START, END
from .state import AgentState
from .config import DatabricksConfig, LLMConfig
from .sql_generator import SQLGenerator
from .tools import DatabricksSQLExecutor, format_table_schemas_for_llm


class SQLDataAgent:
    """Orchestrates the SQL data agent workflow using LangGraph."""

    def __init__(
        self,
        db_config: DatabricksConfig = None,
        llm_config: LLMConfig = None,
    ):
        """Initialize agent with Databricks and LLM config.

        Args:
            db_config: DatabricksConfig, or None to load from env
            llm_config: LLMConfig, or None to load from env
        """
        self.db_config = db_config or DatabricksConfig.from_env()
        self.llm_config = llm_config or LLMConfig.from_env()

        self.sql_generator = SQLGenerator(self.llm_config)
        self.sql_executor = DatabricksSQLExecutor(self.db_config)

        self.graph = self._build_graph()

    def _build_graph(self):
        """Build the LangGraph workflow.

        Workflow:
        START → analyze_question → generate_sql → validate_sql
                                     ↑               ↓
                                     └── (invalid) ──┘
                                                    ↓
                                            execute_sql
                                                    ↓
                                         generate_answer
                                                    ↓
                                                  END

        This explicit routing makes the control flow obvious in interviews.
        """
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("analyze_question", self._analyze_question)
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("validate_sql", self._validate_sql)
        workflow.add_node("execute_sql", self._execute_sql)
        workflow.add_node("generate_answer", self._generate_answer)

        # Add edges
        workflow.add_edge(START, "analyze_question")
        workflow.add_edge("analyze_question", "generate_sql")
        workflow.add_edge("generate_sql", "validate_sql")

        # Conditional routing: if validation fails and we can retry, go back
        workflow.add_conditional_edges(
            "validate_sql",
            self._should_retry,
            {
                "retry": "generate_sql",
                "execute": "execute_sql",
                "abort": "generate_answer",
            },
        )

        workflow.add_edge("execute_sql", "generate_answer")
        workflow.add_edge("generate_answer", END)

        return workflow.compile()

    @staticmethod
    def _analyze_question(state: AgentState) -> AgentState:
        """Analyze the question to understand intent and identify relevant tables.

        Args:
            state: Current agent state

        Returns:
            Updated state with table analysis
        """
        # Simple analysis: identify key terms
        question = state.question.lower()

        relevant_tables = []
        if any(word in question for word in ["adoption", "active", "users"]):
            relevant_tables.append("product_adoption")
        if any(word in question for word in ["engagement", "engaged", "customer"]):
            relevant_tables.append("customer_engagement")
        if any(word in question for word in ["support", "issue", "demand", "request"]):
            relevant_tables.append("support_metrics")

        table_analysis = f"Relevant tables: {', '.join(relevant_tables) if relevant_tables else 'Unknown - will infer from question'}"

        state.table_analysis = table_analysis
        state.table_schemas = {"schemas": format_table_schemas_for_llm()}

        return state

    def _generate_sql(self, state: AgentState) -> AgentState:
        """Generate SQL query from natural language question.

        Args:
            state: Current agent state

        Returns:
            Updated state with generated SQL
        """
        sql_query, reasoning = self.sql_generator.generate(state.question)
        state.sql_query = sql_query
        return state

    @staticmethod
    def _validate_sql(state: AgentState) -> AgentState:
        """Validate SQL query for safety before execution.

        Args:
            state: Current agent state

        Returns:
            Updated state with validation result
        """
        from .validators import SQLValidator

        validator = SQLValidator()
        is_valid, error_msg = validator.validate(state.sql_query)

        state.is_valid = is_valid
        state.validation_error = error_msg if not is_valid else ""

        return state

    def _should_retry(self, state: AgentState) -> str:
        """Decide what to do after validation.

        Returns:
            "retry" - go back to generate_sql
            "execute" - proceed to execute_sql
            "abort" - give up and go to generate_answer with error
        """
        if state.is_valid:
            return "execute"

        if state.should_retry():
            state.increment_retry()
            return "retry"

        return "abort"

    def _execute_sql(self, state: AgentState) -> AgentState:
        """Execute validated SQL query against Databricks.

        Args:
            state: Current agent state (with valid SQL)

        Returns:
            Updated state with query results or error
        """
        success, results, error = self.sql_executor.execute(state.sql_query)

        state.sql_result = results if success else None
        state.sql_error = error if not success else ""

        return state

    @staticmethod
    def _generate_answer(state: AgentState) -> AgentState:
        """Generate business-friendly answer from results.

        Args:
            state: Current agent state

        Returns:
            Updated state with final answer
        """
        if state.sql_error:
            state.final_answer = (
                f"Failed to execute query: {state.sql_error}\n"
                f"Validation error: {state.validation_error}"
            )
        elif state.sql_result is not None:
            # Format results as business answer
            result_count = len(state.sql_result)
            if result_count == 0:
                state.final_answer = "No results found for your query."
            else:
                # Show first few rows
                lines = [
                    f"Found {result_count} result(s):",
                    "",
                ]
                for i, row in enumerate(state.sql_result[:10]):
                    lines.append(f"Result {i+1}: {row}")
                    if i >= 9:
                        if result_count > 10:
                            lines.append(f"... and {result_count - 10} more results")
                        break

                state.final_answer = "\n".join(lines)
        else:
            state.final_answer = (
                "Unable to generate answer. "
                f"Validation error: {state.validation_error}"
            )

        return state

    def run(self, question: str) -> dict:
        """Execute the agent for a given question.

        Args:
            question: Natural language business question

        Returns:
            Dict with final state including question, sql_query, sql_result, final_answer
        """
        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError("Agent execution timed out after 60 seconds")

        # Set 300 second (5 minute) timeout for Databricks queries
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(300)

        try:
            initial_state = AgentState(question=question)
            print(f"DEBUG: Invoking graph with state: question={question[:50]}...", flush=True)
            final_state = self.graph.invoke(initial_state)
            print("DEBUG: Graph invocation completed", flush=True)
        finally:
            signal.alarm(0)  # Cancel the alarm

        # Handle both dict and AgentState return types
        if isinstance(final_state, dict):
            return final_state

        return {
            "question": final_state.question,
            "table_analysis": final_state.table_analysis,
            "sql_query": final_state.sql_query,
            "is_valid": final_state.is_valid,
            "validation_error": final_state.validation_error,
            "sql_result": final_state.sql_result,
            "sql_error": final_state.sql_error,
            "retry_count": final_state.retry_count,
            "final_answer": final_state.final_answer,
        }
