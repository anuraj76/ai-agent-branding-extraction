# Enterprise Product Support Intelligence Agent - Phase 3

## Problem Statement

Business users need to analyze product data to answer questions like:
- "Which products have the highest adoption?"
- "Which products have high usage but also high support demand?"
- "Which customers are most engaged?"

Rather than learning SQL, they should ask in natural language and get data-driven answers.

**Phase 3 Goal**: Build a LangGraph-based SQL data agent that can:
1. Understand natural language business questions
2. Generate safe SQL queries automatically
3. Execute queries against Databricks/Unity Catalog
4. Validate results and return business-friendly answers

## Why LangGraph?

LangGraph is ideal for this use case because:

1. **Explicit State Management**: We have a clear data flow (question → SQL → result) that is easy to track
2. **Conditional Routing**: Invalid SQL can be routed back to regeneration instead of blindly executing
3. **Visibility**: The graph structure makes the control flow obvious—critical for interviews and debugging
4. **Type Safety**: State is strongly typed, preventing subtle bugs

Compare to alternatives:
- **Raw LangChain chains**: Less visible control flow, harder to handle failures
- **Custom orchestration**: More code, more bugs
- **LangGraph**: Clear nodes and edges that map to the workflow

## Architecture

### High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Enterprise Product Support Agent                │
│                        (LangGraph Orchestrator)                      │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ↓                             ↓
            ┌──────────────┐         ┌────────────────────┐
            │  User Input  │         │  Configuration     │
            │   Question   │         │  - Databricks      │
            └──────────────┘         │  - OpenAI (LLM)    │
                    │                │  - Approved Tables │
                    ↓                └────────────────────┘
         ┌──────────────────────┐
         │  LangGraph Workflow  │
         │   (5 Nodes, State)   │
         └──────────────────────┘
                    │
        ┌───────────┼───────────┐
        ↓           ↓           ↓
    ┌────────────────────────────────────┐
    │  SQL Generation & Validation Layer │
    │                                    │
    │  • Schema Exposure                │
    │  • LLM (OpenAI gpt-4o-mini)       │
    │  • 4-Layer Validation             │
    └────────────────────────────────────┘
                    │
                    ↓
    ┌────────────────────────────────────┐
    │  Databricks SQL Execution Layer    │
    │                                    │
    │  • SQL Connector                  │
    │  • Query Execution                │
    │  • Result Processing              │
    └────────────────────────────────────┘
                    │
                    ↓
         ┌──────────────────────┐
         │  Business-Friendly   │
         │  Result Formatting   │
         └──────────────────────┘
                    │
                    ↓
         ┌──────────────────────┐
         │   Final Answer       │
         │   (to Business User) │
         └──────────────────────┘
```

### LangGraph Node Flow (Execution Path)

```
User Question
    ↓
[analyze_question] - Identify relevant tables
    ↓
[generate_sql] - LLM creates SQL from question
    ↓
[validate_sql] - Check safety (SELECT only, approved tables)
    ↓
    ├─ Invalid? → Retry [generate_sql] (up to 2 times)
    │
[execute_sql] - Run SQL on Databricks
    ↓
[generate_answer] - Format results for business user
    ↓
Final Answer
```

### Component Interaction Diagram

```
┌────────────────────────────────────────────────────────────┐
│                        AgentState                          │
│  (Flows through all nodes, updated at each step)          │
│                                                            │
│  • question → table_analysis → sql_query → is_valid       │
│  • validation_error → sql_result → sql_error              │
│  • retry_count → final_answer                             │
└────────────────────────────────────────────────────────────┘
         ▲              ▲             ▲              ▲
         │              │             │              │
    ┌────┴────┐    ┌────┴────┐  ┌────┴────┐   ┌────┴────┐
    │ Node 1  │    │ Node 2  │  │ Node 3  │   │ Node 4  │
    │ Analyze │───▶│Generate │─▶│Validate │──▶│Execute  │
    │Question │    │   SQL   │  │   SQL   │   │  SQL    │
    └─────────┘    └─────────┘  └────┬────┘   └────┬────┘
                                      │              │
                            ┌─────────┘              │
                            │ Invalid?              │
                            │ & Retries?             │
                            ▼                        │
                      [Retry Loop]                  │
                            │                        │
                            └────────────────────────┘
                                        │
                                    ┌───▼────┐
                                    │ Node 5 │
                                    │Generate│
                                    │Answer  │
                                    └────────┘
                                        │
                                        ▼
                                  Final Answer
```

### Security & Validation Layers

```
                  SQL Query Generated
                          │
    ┌───────────────────────┼───────────────────────┐
    │                       │                       │
    ▼                       ▼                       ▼
Layer 1              Layer 2                 Layer 3
Prompt Eng.      Keyword Check          Table Access
    │                   │                       │
LLM sees only    Reject INSERT,         Only workspace.
approved tables  UPDATE, DELETE,     digital_product.*
                 DROP, ALTER, etc.
    │                   ▼                       │
    │           Multiple Statements?            │
    │           (Semicolon Detection)           │
    │                   │                       ▼
    └───────────────────┼──────────────────────┐
                        │                      │
                        ▼                      ▼
                    Layer 4
                Statement Check
                  SELECT only?
                        │
                        ▼
                  ✓ VALID SQL
                        │
                    Re-Validate
                 (Before Execute)
                        │
                        ▼
                   EXECUTE
```

### Data Flow Through State

The `AgentState` carries all relevant information through the graph:

```python
@dataclass
class AgentState:
    question: str                      # Input
    table_analysis: str                # analyze_question output
    sql_query: str                     # generate_sql output
    is_valid: bool                     # validate_sql output
    validation_error: str              # If validation fails
    sql_result: Optional[list[dict]]   # execute_sql output
    sql_error: str                     # If execution fails
    retry_count: int                   # Track retries
    final_answer: str                  # generate_answer output
```

## How Databricks / Unity Catalog Is Used

### Approved Tables

The agent has access to 3 gold tables in `workspace.digital_product`:

1. **product_adoption**
   - `product_id`, `product_name`, `adoption_rate`, `active_users`, `date`
   - Used for: Adoption trends, user growth

2. **customer_engagement**
   - `customer_id`, `product_id`, `engagement_score`, `last_activity_date`, `total_sessions`
   - Used for: Customer engagement analysis

3. **support_metrics**
   - `product_id`, `support_requests`, `avg_resolution_time_hours`, `critical_issues`, `date`
   - Used for: Support demand analysis

### Schema Exposure

The LLM is given:
- Full table names (e.g., `workspace.digital_product.product_adoption`)
- Column names and types
- Business descriptions

This prevents hallucinating columns while keeping the LLM guided by actual schema.

### Read-Only Execution

The SQL validator ensures:
- ✗ No INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, MERGE
- ✗ No multiple statements (semicolon check)
- ✓ Only SELECT queries
- ✓ Only approved tables
- ✓ Only approved schema

## Security Considerations

### What We Protect Against

1. **Destructive SQL**: Validator rejects INSERT/UPDATE/DELETE
2. **Multi-statement attacks**: Can't chain multiple queries with `;`
3. **Unauthorized table access**: Only approved tables in `workspace.digital_product`
4. **Prompt injection via data**: Results are never fed back to LLM (we just format them)

### What We Don't (Yet) Protect Against

- **SQL injection**: We trust the LLM to generate clean SQL (production would use parameterized queries)
- **Resource limits**: Large queries could be slow (production would add timeouts)
- **Sensitive data masking**: We return all columns (production would apply column-level security)

## Setup Instructions

### 1. Install Dependencies

```bash
# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies using uv
uv pip install -e .
```

### 2. Get OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Create a new API key (or use existing)
3. Copy the key (you'll only see it once)

### 3. Configure Databricks

Get your connection details from Databricks:
1. Go to **Admin Console** → **Compute** → **SQL Warehouses**
2. Click your warehouse
3. Copy: **Server hostname** (DATABRICKS_HOST)
4. Copy: **HTTP path** (DATABRICKS_HTTP_PATH)
5. Go to **Settings** → **Developer** → **Access tokens**
6. Create a new token and copy it (DATABRICKS_TOKEN)

### 4. Set Environment Variables

```bash
# Copy the example
cp .env.example .env

# Edit .env with your values
DATABRICKS_HOST=adb-1234567890.azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/warehouse_id
DATABRICKS_TOKEN=dapi1234567890abcdef...
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
```

### 5. Verify Setup (Optional)

```bash
python -c "from src.support_agent.config import DatabricksConfig, LLMConfig; print('Databricks:', DatabricksConfig.from_env()); print('LLM:', LLMConfig.from_env())"
```

Should print your config without errors.

## Running the Agent

### Basic Usage

```bash
python main.py "Which products have the highest adoption?"
```

### Custom Question

```bash
python main.py "Which products have high usage but also high support demand?"
```

### Output Example

```
================================================================================
Question: Which products have the highest adoption?
================================================================================

Table Analysis:
  Relevant tables: product_adoption

Generated SQL:
SELECT 
  product_name,
  adoption_rate,
  active_users
FROM workspace.digital_product.product_adoption
ORDER BY adoption_rate DESC
LIMIT 10

Validation: ✓ PASSED

Final Answer:
Found 3 result(s):
Result 1: {'product_name': 'Premium Suite', 'adoption_rate': 0.95, 'active_users': 5420}
Result 2: {'product_name': 'Analytics Pro', 'adoption_rate': 0.87, 'active_users': 3210}
Result 3: {'product_name': 'Mobile Client', 'adoption_rate': 0.72, 'active_users': 1890}
================================================================================
```

## Example Execution Flow

### Question
```
"Which products have high usage but also high support demand?"
```

### Step-by-step

1. **analyze_question** node identifies:
   - "high usage" → `product_adoption` table
   - "high support demand" → `support_metrics` table

2. **generate_sql** node:
   - Sends question + table schemas to OpenAI's gpt-4o-mini
   - LLM generates:
     ```sql
     SELECT 
       pa.product_name,
       pa.active_users,
       sm.support_requests,
       sm.avg_resolution_time_hours
     FROM workspace.digital_product.product_adoption pa
     JOIN workspace.digital_product.support_metrics sm 
       ON pa.product_id = sm.product_id
     WHERE pa.active_users > 1000 
       AND sm.support_requests > 100
     ORDER BY sm.support_requests DESC
     LIMIT 10
     ```

3. **validate_sql** node:
   - ✓ Starts with SELECT
   - ✓ Uses only approved tables
   - ✓ No dangerous keywords
   - ✓ No multiple statements
   - Result: **VALID**

4. **execute_sql** node:
   - Connects to Databricks via `databricks-sql-connector`
   - Executes query
   - Returns list of result dicts

5. **generate_answer** node:
   - Formats results for business user
   - Shows product names, usage, and support demand

### Retry Example

If the LLM generates invalid SQL (e.g., references a non-existent column):

1. **validate_sql** returns `is_valid=False`
2. **_should_retry()** checks: `retry_count < max_retries`?
3. If yes → route back to **generate_sql** (try again)
4. If no → route to **generate_answer** with error message

## Project Structure

```
langgraph-advance/
│
├── README.md                      # This file
├── pyproject.toml                 # Project metadata and dependencies
├── .env.example                   # Environment variable template
├── .gitignore
│
├── main.py                        # Entry point for testing
│
└── src/support_agent/
    ├── __init__.py
    │
    ├── config.py                  # Databricks + LLM configuration
    │                              # Approved tables definition
    │
    ├── state.py                   # AgentState dataclass
    │                              # State transitions through graph
    │
    ├── validators.py              # SQL safety validation
    │                              # Dangerous keyword detection
    │                              # Table access control
    │
    ├── tools.py                   # Databricks SQL executor
    │                              # Schema formatting for LLM
    │
    ├── sql_generator.py           # LLM-based SQL generation (OpenAI)
    │                              # Response parsing
    │
    └── agent.py                   # Main LangGraph orchestration
                                   # Node implementations
                                   # Graph construction
```

## File Explanations

### config.py

**Purpose**: Centralized configuration management with multi-provider LLM support

**Key Classes**:
- `DatabricksConfig`: Connection details (host, path, token, catalog, schema)
- `LLMConfig`: Model configuration (provider, model name, temperature, max_tokens, api_key)
- `APPROVED_TABLES`: Dict mapping table names to schemas and columns

**Why it exists**: 
- Keeps secrets out of code
- Makes config testable
- Supports multiple LLM providers (OpenAI now, Bedrock support ready)

**What calls it**: `agent.py` (in `__init__`), `sql_generator.py`

### state.py

**Purpose**: Define the state object that flows through LangGraph

**Key Class**:
- `AgentState`: Dataclass with fields for each stage of the workflow

**Why it exists**: Strong typing prevents bugs, makes state transitions explicit

**What calls it**: `agent.py` (nodes accept/return AgentState)

### validators.py

**Purpose**: SQL safety validation before execution

**Key Class**:
- `SQLValidator`: Checks for dangerous keywords, multiple statements, unapproved tables

**Methods**:
- `validate()`: Main entry point, returns (is_valid, error_message)
- `_check_dangerous_keywords()`: Rejects INSERT, UPDATE, DELETE, etc.
- `_check_multiple_statements()`: Ensures single query
- `_check_table_access()`: Ensures only approved tables
- `_check_select_only()`: Ensures SELECT query

**Why it exists**: Prevents malicious or accidental SQL execution

**What calls it**: `agent.py` (in `_validate_sql` node), `tools.py` (before execution)

### tools.py

**Purpose**: Database interaction and schema utilities

**Key Classes**:
- `DatabricksSQLExecutor`: Executes SQL on Databricks, handles errors gracefully

**Functions**:
- `format_table_schemas_for_llm()`: Returns readable schema description for LLM prompt

**Why it exists**: Separates database interaction from orchestration logic

**What calls it**: `agent.py` (in `_execute_sql` node), `sql_generator.py` (for context)

### sql_generator.py

**Purpose**: Generate SQL from natural language using OpenAI LLM

**Key Class**:
- `SQLGenerator`: Takes question, produces SQL query using gpt-4o-mini

**Methods**:
- `generate()`: Main method, returns (sql_query, reasoning)
- `_extract_sql()`: Parses SQL from LLM response

**Why it exists**: Encapsulates all LLM interaction for SQL generation

**What calls it**: `agent.py` (in `_generate_sql` node)

**System Prompt Contains**:
- Instruction to use only approved tables
- Requirement for SELECT-only queries
- Table schemas and column descriptions
- Instructions to never invent columns

### agent.py

**Purpose**: Main orchestration using LangGraph

**Key Class**:
- `SQLDataAgent`: Builds and executes the graph

**Nodes** (graph steps):
1. `analyze_question`: Identify relevant tables
2. `generate_sql`: LLM creates SQL (via OpenAI)
3. `validate_sql`: Safety check
4. `execute_sql`: Run on Databricks
5. `generate_answer`: Format results

**Routing Logic**:
- START → `analyze_question` → `generate_sql` → `validate_sql`
- If invalid & retries left: → `generate_sql` (loop)
- If invalid & no retries left: → `generate_answer` (with error)
- If valid: → `execute_sql` → `generate_answer` → END

**Why it exists**: Central orchestration point, makes control flow explicit

**What calls it**: `main.py` invokes `SQLDataAgent.run(question)`

## Testing

### Manual Testing Strategy

Since we're testing manually, here's how to test:

#### Test 1: Valid Query on Real Table

```bash
python main.py "Which products have the highest adoption?"
```

Expected: SQL executes successfully, returns results.

#### Test 2: Invalid SQL (Non-existent Column)

The LLM might generate a query with a wrong column. The validator should catch it, retry, and eventually give an error if retries exhaust.

```bash
python main.py "What is the customer satisfaction score by product?"
```

(Note: `customer_satisfaction_score` doesn't exist—LLM should figure this out or error)

#### Test 3: Ambiguous Question

```bash
python main.py "Show me the data"
```

Expected: LLM might generate a generic SELECT; system should return data if valid.

### Validator Tests (Manual)

Edit `main.py` temporarily to test validator directly:

```python
from src.support_agent.validators import SQLValidator

validator = SQLValidator()

# Test 1: DELETE should fail
print(validator.validate("DELETE FROM workspace.digital_product.product_adoption"))
# Expected: (False, "Query contains dangerous keyword: DELETE")

# Test 2: Multiple statements should fail
print(validator.validate("SELECT * FROM t1; SELECT * FROM t2"))
# Expected: (False, "Query contains multiple statements")

# Test 3: Unapproved table should fail
print(validator.validate("SELECT * FROM workspace.other_schema.products"))
# Expected: (False, "Query references unapproved table")

# Test 4: Valid query should pass
print(validator.validate(
    "SELECT product_name FROM workspace.digital_product.product_adoption LIMIT 10"
))
# Expected: (True, "")
```

## Example Interview Explanation

**Interviewer**: "Why use LangGraph instead of just chaining LangChain tools?"

**You**:

> LangGraph gives us explicit state management and conditional routing. Here's why that matters:
>
> **State Management**: Every piece of data flowing through the agent is captured in our `AgentState` dataclass—the question, generated SQL, validation result, execution result, and final answer. This makes debugging easy: we can print the state at any node and see exactly what happened.
>
> **Conditional Routing**: If SQL validation fails, instead of blindly executing bad SQL, we check if we can retry. If we have retries left, we route back to SQL generation. If we're out of retries, we route to answer generation with an error. This routing logic is explicit in the graph—you can see it as edges in the workflow.
>
> **Visibility**: The graph structure is obvious. I can explain it in 30 seconds: "question → analyze → generate SQL → validate → [if invalid: retry] → execute → answer." A chain of tools is less clear.
>
> This matters in production because bugs are easier to find (state is visible), and in interviews because it shows I understand orchestration patterns.

---

**Interviewer**: "How do you prevent the LLM from generating dangerous SQL?"

**You**:

> Three layers:
>
> 1. **Prompt engineering**: The system prompt tells the LLM it can only use approved tables and SELECT queries. It includes the actual table schemas so it doesn't hallucinate columns.
>
> 2. **Input validation**: After the LLM generates SQL, our `SQLValidator` checks for dangerous keywords (INSERT, UPDATE, DELETE, DROP, ALTER, etc.), multiple statements, and unapproved tables.
>
> 3. **Execution control**: Even if validation passed, the `DatabricksSQLExecutor` validates again before executing. The validator rejects anything that's not a SELECT.
>
> Could an LLM still generate bad SQL? Yes—but we'd catch it in validation and either retry or error gracefully. In production, I'd add parameterized queries and query timeouts.

---

**Interviewer**: "What happens if the LLM generates SQL with a non-existent column?"

**You**:

> Good question. Here's the flow:
>
> 1. LLM sees table schemas including column names
> 2. LLM generates SQL (ideally without hallucinating)
> 3. Validator passes it (there's no column existence check—we trust the LLM here)
> 4. Executor runs query on Databricks
> 5. Databricks returns an error: "Column X not found"
> 6. Executor catches the error and returns it to state as `sql_error`
> 7. `generate_answer` node formats the error as a business-friendly message
>
> Ideally, the LLM wouldn't generate invalid SQL if it sees the real schema. If it does, that's a sign we need to improve the prompt or use a better model.
>
> In production, I'd add a post-validation step that checks if the SQL actually runs against the schema (dry-run), and if not, trigger a retry with the error message.

---

**Interviewer**: "Why OpenAI instead of a different provider?"

**You**:

> I chose OpenAI (gpt-4o-mini) because:
>
> 1. **Cost**: gpt-4o-mini is affordable for experimentation
> 2. **Performance**: Strong SQL generation from good quality models
> 3. **Simplicity**: Straightforward API integration via LangChain
>
> However, the architecture is provider-agnostic. The `LLMConfig` has a `provider` field, and `SQLGenerator` can switch between OpenAI, Bedrock (AWS), or other providers by changing the initialization logic. The SQL generation logic itself doesn't care which provider we use—it's just asking "convert this question to SQL."
>
> For production, I might use a cheaper model like Bedrock's hosted Claude for cost optimization, or a locally-hosted model for data privacy.

## Current Limitations

1. **LLM Hallucination**: LLM might still generate SQL with non-existent columns (mitigated by schema exposure, but not prevented)
2. **No Param Queries**: SQL is generated as strings (vulnerable to injection if LLM is compromised)
3. **No Query Optimization**: LLM might generate inefficient queries (could add a query analyzer node)
4. **No Caching**: Every question requires LLM call + DB query (could add result caching)
5. **Single Retry Strategy**: Max 2 retries is arbitrary (could make adaptive)
6. **No Multi-step Reasoning**: Complex questions requiring joins across multiple tables might confuse the LLM

## Future Phases

- **Phase 4**: Add result explanation using LLM (interpret business meaning of query results)
- **Phase 5**: Add RAG for company-specific business definitions (e.g., what "high adoption" means)
- **Phase 6**: Multi-agent approach with separate Query Planner, SQL Expert, Result Analyzer
- **Phase 7**: GraphRAG for complex relationship queries
- **Phase 8**: Frontend for business users (web UI)

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| langraph | ≥0.1.0 | LangGraph orchestration |
| langchain | ≥0.2.0 | LangChain base utilities |
| langchain-core | ≥0.2.0 | Core LangChain types |
| langchain-openai | ≥0.1.0 | OpenAI integration (gpt-4o-mini, etc) |
| databricks-sql-connector | ≥3.0.0 | Databricks SQL connection |
| python-dotenv | ≥1.0.0 | Environment variable loading |
| pydantic | ≥2.0.0 | Data validation |
| typing-extensions | ≥4.0.0 | Python 3.11 type hints |

## License

Portfolio project by Anuraj
