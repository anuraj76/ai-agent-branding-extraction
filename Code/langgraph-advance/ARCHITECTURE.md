# Phase 3 Architecture Deep Dive

## Complete Code Walkthrough

### 1. config.py - Configuration Management

**Purpose**: Centralize all configuration and keep secrets out of code

**Key Components**:

#### DatabricksConfig
```python
@dataclass
class DatabricksConfig:
    host: str                          # e.g., adb-1234567890.azuredatabricks.net
    http_path: str                     # e.g., /sql/1.0/warehouses/warehouse_id
    token: str                         # Personal access token (secret)
    catalog: str = "workspace"         # Default catalog
    schema: str = "digital_product"    # Default schema
```

**Why it exists**: 
- Separates credentials from logic
- Makes testing easier (can mock or override)
- Single source of truth for connection details

**How it's used**:
```python
config = DatabricksConfig.from_env()  # Loads from .env
executor = DatabricksSQLExecutor(config)  # Passed to executor
```

#### LLMConfig (Provider-Agnostic)
```python
@dataclass
class LLMConfig:
    provider: str = "openai"           # "openai", "bedrock" (future)
    model: str = "gpt-4o-mini"         # OpenAI model name
    temperature: float = 0.0           # Deterministic responses
    max_tokens: int = 1024             # Limit response length
    api_key: Optional[str] = None      # OpenAI API key
```

**Why provider is important**:
- **Interview point**: "I chose OpenAI but the architecture supports other providers"
- **Future-proof**: When AWS Bedrock support is added, only `sql_generator.py` changes
- **Cost optimization**: Could switch to cheaper Bedrock Claude for production

**How it validates**:
```python
if provider == "openai" and not api_key:
    raise ValueError("OpenAI provider selected but OPENAI_API_KEY not set")
```

#### APPROVED_TABLES (Schema Dictionary)
```python
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
    # ... more tables
}
```

**Why it exists**:
- Single source of truth for approved tables
- Prevents LLM from accessing restricted tables
- Can be passed to validator and LLM

**How it's used**:
```python
# In SQLValidator
validator = SQLValidator(approved_tables=APPROVED_TABLES)

# In SQL Generator system prompt
table_schemas_text = format_table_schemas_for_llm()
# This formats the above dict into readable prompt text
```

---

### 2. state.py - LangGraph State Definition

**Purpose**: Define the data structure that flows through the LangGraph

```python
@dataclass
class AgentState:
    question: str                      # Stage 1: User input
    table_analysis: str                # Stage 2: Which tables are relevant?
    sql_query: str                     # Stage 3: Generated SQL
    is_valid: bool                     # Stage 4: Passed validation?
    validation_error: str              # Stage 4: Why it failed
    sql_result: Optional[list[dict]]   # Stage 5: Query results
    sql_error: str                     # Stage 5: Execution error
    retry_count: int                   # Stage 3-4: How many retries so far?
    final_answer: str                  # Stage 6: Business-friendly response
```

**Why this matters**:
- **Type safety**: Each field has a type; Python catches mistakes
- **Traceability**: At any point, you can print the state and see all intermediate results
- **Interview advantage**: "This state makes debugging trivial"

**Example state at each stage**:

After `analyze_question`:
```python
AgentState(
    question="Which products have high adoption?",
    table_analysis="Relevant tables: product_adoption",
    sql_query="",
    # ...
)
```

After `generate_sql`:
```python
AgentState(
    question="Which products have high adoption?",
    table_analysis="Relevant tables: product_adoption",
    sql_query="SELECT product_name, adoption_rate FROM workspace.digital_product.product_adoption ORDER BY adoption_rate DESC",
    # ...
)
```

After `validate_sql`:
```python
AgentState(
    # ... previous fields ...
    sql_query="SELECT product_name, adoption_rate FROM workspace.digital_product.product_adoption ORDER BY adoption_rate DESC",
    is_valid=True,
    validation_error="",
    # ...
)
```

After `execute_sql`:
```python
AgentState(
    # ... previous fields ...
    sql_result=[
        {"product_name": "Premium Suite", "adoption_rate": 0.95},
        {"product_name": "Analytics Pro", "adoption_rate": 0.87},
    ],
    sql_error="",
    # ...
)
```

After `generate_answer`:
```python
AgentState(
    # ... all previous fields ...
    final_answer="Found 2 result(s):\nResult 1: {'product_name': 'Premium Suite', 'adoption_rate': 0.95}\n...",
)
```

---

### 3. validators.py - SQL Safety Validation

**Purpose**: Prevent dangerous or malicious SQL from executing

**Core Validation Layers**:

#### Layer 1: Dangerous Keywords
```python
DANGEROUS_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "MERGE", "EXEC", "EXECUTE", "SCRIPT"
}

def _check_dangerous_keywords(self, sql_query: str):
    query_upper = sql_query.upper()
    for keyword in self.DANGEROUS_KEYWORDS:
        if re.search(rf"\b{keyword}\b", query_upper):
            return f"Query contains dangerous keyword: {keyword}"
```

**Why regex boundary `\b`?**
- Prevents false positives: "UPDATE" in column name "status_update" won't trigger
- `\b` means word boundary, so only whole words match

**Interview point**: "I reject destructive SQL by keyword matching. This is simple but effective."

#### Layer 2: Single Statement Check
```python
def _check_multiple_statements(self, sql_query: str):
    parts = sql_query.split(";")
    if len(parts) > 2:
        return "Query contains multiple statements (semicolon detected)"
    if len(parts) == 2 and parts[1].strip():
        return "Query contains multiple statements"
```

**Why?** Prevents chaining: `SELECT * FROM t1; DELETE FROM t2`

**Limitation**: Doesn't catch stored procedures or other multi-statement tricks (future: regex parse query structure)

#### Layer 3: Table Access Control
```python
def _check_table_access(self, sql_query: str):
    # Extract table names from FROM and JOIN clauses
    from_pattern = r"FROM\s+(\S+)"
    join_pattern = r"JOIN\s+(\S+)"
    
    tables_in_query = set()
    # ... extract tables ...
    
    for table in tables_in_query:
        table_normalized = table.lower()
        is_approved = any(
            approved.lower() == table_normalized
            for approved in self.approved_table_names
        )
        if not is_approved:
            return f"Query references unapproved table: {table}"
```

**Why it matters**: 
- User can't query sensitive tables (e.g., `sys.secrets`, `admin_logs`)
- Only approved tables listed in `APPROVED_TABLES`

**Example**:
- `"SELECT * FROM workspace.digital_product.product_adoption"` → ✓ APPROVED
- `"SELECT * FROM workspace.admin.secrets"` → ✗ REJECTED

#### Layer 4: SELECT-Only Check
```python
def _check_select_only(self, sql_query: str):
    query_stripped = sql_query.strip()
    if not query_stripped.upper().startswith("SELECT"):
        return "Query must be a SELECT statement"
```

**Simple but effective**: Catches obvious violations

**Public API**:
```python
def validate(self, sql_query: str) -> tuple[bool, str]:
    """Main entry point. Returns (is_valid, error_message)"""
    # Run all checks in order
    is_valid, error_msg = validator.validate(sql_query)
    if not is_valid:
        print(f"SQL rejected: {error_msg}")
```

---

### 4. tools.py - Database Access & Schema Utilities

**Purpose**: Encapsulate all database interaction and schema formatting

#### DatabricksSQLExecutor
```python
class DatabricksSQLExecutor:
    def __init__(self, config: DatabricksConfig):
        self.config = config
        self.validator = SQLValidator()  # Validates before executing

    def execute(self, sql_query: str) -> tuple[bool, Optional[List[dict]], str]:
        """
        Returns: (success, results, error_message)
        - success: True if query ran without error
        - results: List of dict rows if successful, None if failed
        - error_message: Description of failure if any
        """
        # Validation happens AGAIN here (defense in depth)
        is_valid, error_msg = self.validator.validate(sql_query)
        if not is_valid:
            return False, None, error_msg
        
        # Connect to Databricks
        with sql.connect(
            server_hostname=self.config.host,
            http_path=self.config.http_path,
            personal_access_token=self.config.token,
        ) as connection:
            cursor = connection.cursor()
            cursor.execute(sql_query)
            results = cursor.fetchall()
            
            # Convert tuples to dicts (better for JSON serialization)
            columns = [desc[0] for desc in cursor.description]
            result_dicts = [dict(zip(columns, row)) for row in results]
            cursor.close()
        
        return True, result_dicts, ""
```

**Why re-validate at execution?**
- **Defense in depth**: Multiple validation layers reduce risk
- **Interview point**: "Even if validation was bypassed, we validate again"

**Error handling**:
```python
except sql.Error as e:
    return False, None, f"Databricks SQL error: {str(e)}"
except Exception as e:
    return False, None, f"Unexpected error: {str(e)}"
```

Catches and returns errors gracefully—doesn't crash the agent.

#### Schema Formatting
```python
def format_table_schemas_for_llm() -> str:
    """
    Convert the APPROVED_TABLES dict into a readable prompt.
    
    Output looks like:
    
    Available tables in workspace.digital_product schema:
    
    Table: product_adoption
    Full name: workspace.digital_product.product_adoption
    Description: Product adoption metrics and trends
    Columns:
      - product_id: str - Unique product identifier
      - product_name: str - Product name
      - adoption_rate: float - Adoption rate (0-1)
      - active_users: int - Number of active users
      - date: date - Metric date
    """
    schemas = get_table_schemas()
    lines = []
    lines.append("Available tables in workspace.digital_product schema:")
    # ... format each table ...
    return "\n".join(lines)
```

**Why?**
- LLM sees actual column names → no hallucination
- LLM sees column types → generates compatible SQL
- LLM sees descriptions → understands semantics

**Used in**:
```python
# In SQLGenerator system prompt
table_schemas_text = format_table_schemas_for_llm()
system_prompt = SYSTEM_PROMPT.format(table_schemas=table_schemas_text)
```

---

### 5. sql_generator.py - LLM-Based SQL Generation

**Purpose**: Convert natural language questions to SQL using OpenAI

#### SQLGenerator Class
```python
class SQLGenerator:
    SYSTEM_PROMPT = """You are an expert SQL analyst...
    
    IMPORTANT CONSTRAINTS:
    1. Only use tables from workspace.digital_product schema
    2. Only generate SELECT queries - NO INSERT, UPDATE, DELETE, DROP, ALTER, etc.
    3. NEVER reference tables outside the approved list
    4. NEVER make up column names - use only the columns listed
    5. If the question cannot be answered with available data, say so clearly
    
    {table_schemas}  # <-- Actual schemas injected here
    """
    
    def __init__(self, config: LLMConfig = None):
        self.config = config or LLMConfig.from_env()
        
        # Initialize OpenAI
        if self.config.provider == "openai":
            self.llm = ChatOpenAI(
                model=self.config.model,           # gpt-4o-mini
                temperature=self.config.temperature,  # 0.0 = deterministic
                max_tokens=self.config.max_tokens,
                api_key=self.config.api_key,
            )
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")
```

**Provider abstraction**:
- Current: OpenAI via `langchain_openai.ChatOpenAI`
- Future: Bedrock support would add `elif self.config.provider == "bedrock"`
- The rest of the code doesn't change—only this section

#### SQL Generation
```python
def generate(self, question: str) -> tuple[str, str]:
    """
    Args:
        question: "Which products have the highest adoption?"
    
    Returns:
        (sql_query, reasoning)
        - sql_query: The generated SQL
        - reasoning: LLM's explanation
    """
    table_schemas_text = format_table_schemas_for_llm()
    
    system_prompt = self.SYSTEM_PROMPT.format(
        table_schemas=table_schemas_text
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            f"Generate SQL to answer: {question}\n\n"
            f"Respond with:\n"
            f"1. SQL query in a code block\n"
            f"2. Brief explanation"
        )),
    ]
    
    response = self.llm.invoke(messages)
    response_text = response.content
    
    # Extract SQL from response
    sql_query = self._extract_sql(response_text)
    
    return sql_query, response_text
```

**Flow**:
1. Get table schemas
2. Inject into system prompt
3. Send to OpenAI with user question
4. Extract SQL from response
5. Return SQL + full reasoning

#### SQL Extraction
```python
@staticmethod
def _extract_sql(response_text: str) -> str:
    """
    LLM might respond with:
    
    "Here's the SQL query:
    
    ```sql
    SELECT product_name, adoption_rate
    FROM workspace.digital_product.product_adoption
    ORDER BY adoption_rate DESC
    ```
    
    This query..."
    
    We extract just the SQL.
    """
    # First try: markdown code block
    sql_match = re.search(
        r"```(?:sql)?\s*\n(.*?)\n```",
        response_text,
        re.DOTALL | re.IGNORECASE,
    )
    if sql_match:
        return sql_match.group(1).strip()
    
    # Fallback: look for bare SELECT statement
    select_match = re.search(
        r"(SELECT\s+.*?)(?:\n\n|$)",
        response_text,
        re.DOTALL | re.IGNORECASE,
    )
    if select_match:
        return select_match.group(1).strip()
    
    # Last resort
    return response_text.strip()
```

**Why multiple extraction methods?**
- Different LLMs format responses differently
- Fallback chain ensures we get SQL regardless

---

### 6. agent.py - LangGraph Orchestration

**Purpose**: Wire everything together using LangGraph

#### Graph Structure
```python
class SQLDataAgent:
    def _build_graph(self):
        workflow = StateGraph(AgentState)
        
        # Add 5 nodes (stages of the pipeline)
        workflow.add_node("analyze_question", self._analyze_question)
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("validate_sql", self._validate_sql)
        workflow.add_node("execute_sql", self._execute_sql)
        workflow.add_node("generate_answer", self._generate_answer)
        
        # Wire them up
        workflow.add_edge(START, "analyze_question")
        workflow.add_edge("analyze_question", "generate_sql")
        workflow.add_edge("generate_sql", "validate_sql")
        
        # Conditional routing: key part!
        workflow.add_conditional_edges(
            "validate_sql",
            self._should_retry,  # Decide next node based on state
            {
                "retry": "generate_sql",      # Go back if invalid & retries left
                "execute": "execute_sql",     # Proceed if valid
                "abort": "generate_answer",   # Give up if retries exhausted
            },
        )
        
        workflow.add_edge("execute_sql", "generate_answer")
        workflow.add_edge("generate_answer", END)
        
        return workflow.compile()
```

**Visual flow**:
```
START
  ↓
analyze_question
  ↓
generate_sql ←─┐
  ↓            │ (retry if invalid & retries left)
validate_sql ──┤
  ↓            │
  ├─→ execute_sql ─→ generate_answer ─→ END
  │
  └─→ (if retries exhausted) → generate_answer ─→ END
```

#### Node Implementations

**1. analyze_question**
```python
@staticmethod
def _analyze_question(state: AgentState) -> AgentState:
    """Identify which tables are relevant"""
    question = state.question.lower()
    
    relevant_tables = []
    if any(word in question for word in ["adoption", "active", "users"]):
        relevant_tables.append("product_adoption")
    if any(word in question for word in ["engagement", "engaged"]):
        relevant_tables.append("customer_engagement")
    if any(word in question for word in ["support", "issue", "demand"]):
        relevant_tables.append("support_metrics")
    
    state.table_analysis = f"Relevant tables: {', '.join(relevant_tables)}"
    return state
```

**Simple heuristic**: Look for keywords. This is just a preview—full SQL generation knows better.

**2. generate_sql**
```python
def _generate_sql(self, state: AgentState) -> AgentState:
    """Use OpenAI to generate SQL"""
    sql_query, reasoning = self.sql_generator.generate(state.question)
    state.sql_query = sql_query
    return state
```

**What happens**:
1. self.sql_generator (instance of SQLGenerator)
2. Calls generate(question)
3. OpenAI receives system prompt with table schemas
4. OpenAI returns SQL
5. We store it in state

**3. validate_sql**
```python
@staticmethod
def _validate_sql(state: AgentState) -> AgentState:
    """Check if SQL is safe before execution"""
    validator = SQLValidator()
    is_valid, error_msg = validator.validate(state.sql_query)
    
    state.is_valid = is_valid
    state.validation_error = error_msg if not is_valid else ""
    
    return state
```

**Output**:
- If valid: `state.is_valid = True, state.validation_error = ""`
- If invalid: `state.is_valid = False, state.validation_error = "Query contains..."`

**4. Routing Logic (_should_retry)**
```python
def _should_retry(self, state: AgentState) -> str:
    """Decide: retry, execute, or abort?"""
    if state.is_valid:
        return "execute"  # SQL is good, run it
    
    if state.should_retry():  # retry_count < max_retries?
        state.increment_retry()
        return "retry"  # Go back to generate_sql
    
    return "abort"  # Out of retries, give up
```

**Example path 1 (SQL is valid)**:
```
validate_sql → (is_valid=True) → "execute" → execute_sql
```

**Example path 2 (First attempt invalid, retry succeeds)**:
```
validate_sql → (is_valid=False, retry_count=0) → "retry" 
  → generate_sql → validate_sql → (is_valid=True) → "execute" → execute_sql
```

**Example path 3 (Both attempts invalid)**:
```
validate_sql → (is_valid=False, retry_count=0) → "retry"
  → generate_sql → validate_sql → (is_valid=False, retry_count=1) → "abort"
  → generate_answer (with error)
```

**5. execute_sql**
```python
def _execute_sql(self, state: AgentState) -> AgentState:
    """Run the SQL on Databricks"""
    success, results, error = self.sql_executor.execute(state.sql_query)
    
    state.sql_result = results if success else None
    state.sql_error = error if not success else ""
    
    return state
```

**What self.sql_executor does**:
1. Validates SQL again (defense in depth)
2. Connects to Databricks
3. Executes query
4. Returns results as list of dicts

**6. generate_answer**
```python
@staticmethod
def _generate_answer(state: AgentState) -> AgentState:
    """Format results for business user"""
    if state.sql_error:
        state.final_answer = f"Failed: {state.sql_error}"
    elif state.sql_result is not None:
        result_count = len(state.sql_result)
        lines = [f"Found {result_count} result(s):", ""]
        for i, row in enumerate(state.sql_result[:10]):
            lines.append(f"Result {i+1}: {row}")
        state.final_answer = "\n".join(lines)
    else:
        state.final_answer = f"Error: {state.validation_error}"
    
    return state
```

**Three cases**:
- **Execution error**: Return error message
- **Success**: Format results as table
- **Validation error**: Return why SQL failed

#### Public API
```python
def run(self, question: str) -> dict:
    """Execute the agent and return results"""
    initial_state = AgentState(question=question)
    final_state = self.graph.invoke(initial_state)
    
    return {
        "question": final_state.question,
        "table_analysis": final_state.table_analysis,
        "sql_query": final_state.sql_query,
        "is_valid": final_state.is_valid,
        "sql_result": final_state.sql_result,
        "final_answer": final_state.final_answer,
        # ... more fields
    }
```

**What happens when you call `agent.run("Which products have high adoption?")`**:
1. Creates initial AgentState with the question
2. Invokes the compiled graph
3. State flows through nodes: analyze → generate → validate → [retry?] → execute → answer
4. Returns final state as dict for pretty printing

---

### 7. main.py - Entry Point

**Purpose**: Simple CLI for testing the agent

```python
def main():
    try:
        agent = SQLDataAgent()  # Loads config from .env
        
        # Get question from args or use default
        if len(sys.argv) > 1:
            question = " ".join(sys.argv[1:])
        else:
            question = "Which products have the highest adoption?"
        
        result = agent.run(question)
        print_result(result)
    
    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("Make sure to set: DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN, OPENAI_API_KEY")
```

**Entry point for testing**:
```bash
python main.py "Your question here"
```

---

## Complete Request Flow

### Example: "Which products have the highest adoption?"

**Step 1: User Invokes main.py**
```bash
python main.py "Which products have the highest adoption?"
```

**Step 2: main.py creates SQLDataAgent**
```python
agent = SQLDataAgent()  # Loads from .env:
# - DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN
# - OPENAI_API_KEY
# - LLM_MODEL = "gpt-4o-mini"
```

**Step 3: agent.run(question)**
```python
initial_state = AgentState(question="Which products have the highest adoption?")
final_state = self.graph.invoke(initial_state)
```

**Step 4: Graph execution – Node by node**

**Node 1: analyze_question**
```
Input state:
  question = "Which products have the highest adoption?"
  
Node logic:
  - See "adoption" in question
  - Identify: product_adoption table
  
Output state:
  table_analysis = "Relevant tables: product_adoption"
```

**Node 2: generate_sql**
```
Input state:
  question = "Which products have the highest adoption?"
  table_analysis = "Relevant tables: product_adoption"
  
Node logic:
  1. Format table schemas:
     
     Available tables in workspace.digital_product schema:
     
     Table: product_adoption
     ...
     Columns:
       - product_id: str
       - product_name: str
       - adoption_rate: float
       ...
  
  2. Send to OpenAI:
     System: "You are SQL expert. Use only approved tables..."
     + table schemas
     Human: "Generate SQL for: Which products have highest adoption?"
  
  3. OpenAI responds:
     "Here's the SQL:
     ```sql
     SELECT product_name, adoption_rate 
     FROM workspace.digital_product.product_adoption
     ORDER BY adoption_rate DESC
     LIMIT 10
     ```"
  
  4. Extract SQL
  
Output state:
  sql_query = "SELECT product_name, adoption_rate FROM workspace.digital_product.product_adoption ORDER BY adoption_rate DESC LIMIT 10"
```

**Node 3: validate_sql**
```
Input state:
  sql_query = "SELECT product_name, adoption_rate FROM workspace.digital_product.product_adoption ORDER BY adoption_rate DESC LIMIT 10"
  
Node logic:
  1. Check dangerous keywords: SELECT, FROM, ORDER, LIMIT → ✓ All safe
  2. Check multiple statements: No semicolon → ✓
  3. Check table access: workspace.digital_product.product_adoption → ✓ In APPROVED_TABLES
  4. Check SELECT-only: Starts with SELECT → ✓
  
Output state:
  is_valid = True
  validation_error = ""
```

**Routing decision (_should_retry)**
```
is_valid = True → return "execute"
```

**Node 4: execute_sql**
```
Input state:
  sql_query = "SELECT product_name, adoption_rate FROM workspace.digital_product.product_adoption ORDER BY adoption_rate DESC LIMIT 10"
  is_valid = True
  
Node logic:
  1. Validate SQL again: ✓
  2. Connect to Databricks:
     - Host: adb-1234567890.azuredatabricks.net
     - Path: /sql/1.0/warehouses/warehouse_id
     - Token: dapi...
  3. Execute query:
     cursor.execute("SELECT product_name, adoption_rate FROM ...")
  4. Fetch results:
     [("Premium Suite", 0.95), ("Analytics Pro", 0.87), ("Mobile Client", 0.72)]
  5. Convert to dicts:
     [{"product_name": "Premium Suite", "adoption_rate": 0.95}, ...]
  
Output state:
  sql_result = [
    {"product_name": "Premium Suite", "adoption_rate": 0.95},
    {"product_name": "Analytics Pro", "adoption_rate": 0.87},
    {"product_name": "Mobile Client", "adoption_rate": 0.72},
  ]
  sql_error = ""
```

**Node 5: generate_answer**
```
Input state:
  sql_result = [
    {"product_name": "Premium Suite", "adoption_rate": 0.95},
    ...
  ]
  
Node logic:
  if sql_error:
    return error
  elif sql_result is not None:
    result_count = 3
    lines = ["Found 3 result(s):", ""]
    lines.append("Result 1: {'product_name': 'Premium Suite', 'adoption_rate': 0.95}")
    lines.append("Result 2: {'product_name': 'Analytics Pro', 'adoption_rate': 0.87}")
    lines.append("Result 3: {'product_name': 'Mobile Client', 'adoption_rate': 0.72}")
  
Output state:
  final_answer = "Found 3 result(s):\nResult 1: ...\nResult 2: ...\nResult 3: ..."
```

**Step 5: Return results**
```python
return {
    "question": "Which products have the highest adoption?",
    "table_analysis": "Relevant tables: product_adoption",
    "sql_query": "SELECT product_name, adoption_rate FROM workspace.digital_product.product_adoption ORDER BY adoption_rate DESC LIMIT 10",
    "is_valid": True,
    "validation_error": "",
    "sql_result": [{"product_name": "Premium Suite", "adoption_rate": 0.95}, ...],
    "sql_error": "",
    "retry_count": 0,
    "final_answer": "Found 3 result(s):\nResult 1: {'product_name': 'Premium Suite', 'adoption_rate': 0.95}\n...",
}
```

**Step 6: Print results**
```
================================================================================
Question: Which products have the highest adoption?
================================================================================

Table Analysis:
  Relevant tables: product_adoption

Generated SQL:
SELECT product_name, adoption_rate FROM workspace.digital_product.product_adoption ORDER BY adoption_rate DESC LIMIT 10

Validation: ✓ PASSED

Final Answer:
Found 3 result(s):
Result 1: {'product_name': 'Premium Suite', 'adoption_rate': 0.95}
Result 2: {'product_name': 'Analytics Pro', 'adoption_rate': 0.87}
Result 3: {'product_name': 'Mobile Client', 'adoption_rate': 0.72}
================================================================================
```

---

## Key Interview Talking Points

### 1. State Management
> "LangGraph's state management is the key advantage. Every node updates the state predictably. At any point, I can print the state and see exactly what happened."

### 2. Conditional Routing
> "If SQL validation fails, I check if I have retries left. If yes, I route back to SQL generation. If no, I route to answer generation with an error. This is explicit in the graph—you can see the edges."

### 3. Security Layers
> "I have three security layers:
> 1. Prompt engineering tells the LLM what tables it can use
> 2. Validation checks keywords, table access, and statement count
> 3. The executor validates again before running
> This defense-in-depth approach prevents accidents."

### 4. Provider Agnosticism
> "I chose OpenAI for cost and simplicity, but the architecture supports other providers. The LLMConfig has a `provider` field. To add Bedrock, I'd only change SQLGenerator—the rest of the code doesn't care."

### 5. Schema Exposure
> "Instead of hoping the LLM guesses column names, I give it the real schema. The system prompt includes table names, column names, and types. This prevents hallucination."

### 6. Error Handling
> "Errors are captured and returned gracefully. If Databricks returns 'Column not found', that error flows back through state to the final answer. The agent doesn't crash—it tells the user what went wrong."

---

## Debugging Checklist

| Issue | Debug Steps |
|-------|------------|
| "Missing DATABRICKS credentials" | Check .env file; ensure DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN are set |
| "Missing OPENAI_API_KEY" | Check .env file; ensure OPENAI_API_KEY=sk-... is set |
| "Column X not found" | LLM hallucinated a column. The schema prompt might need refinement, or the LLM needs a better model. Check what columns are actually available in the table. |
| "Query contains dangerous keyword" | Validator rejected the query. Check the generated SQL in output. If it looks OK, the keyword regex might have a false positive. |
| "Query references unapproved table" | LLM used a table outside workspace.digital_product. Check the prompt—it should only suggest approved tables. |
| "Connection refused" | Databricks host/path might be wrong. Verify they're correct from the Databricks UI. |
| "Query timed out" | Databricks query took too long. The SQL might be inefficient or querying too much data. Add LIMIT to reduce results. |

