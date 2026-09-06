# Quick Start Guide

## ⚡ 5 Minute Setup

### 1. Install Dependencies
```bash
cd /Users/aditianuraj/Code/langgraph-advance
python -m venv venv
source venv/bin/activate
uv pip install -e .
```

### 2. Get API Keys

**OpenAI**:
- Go to https://platform.openai.com/api-keys
- Create new secret key
- Copy (starts with `sk-`)

**Databricks**:
- Log into workspace
- Admin Console → Compute → SQL Warehouses
- Copy **Server hostname** (e.g., `adb-...azuredatabricks.net`)
- Copy **HTTP path** (e.g., `/sql/1.0/warehouses/...`)
- Settings → Developer → Access tokens
- Create token, copy it

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your values:
# DATABRICKS_HOST=...
# DATABRICKS_HTTP_PATH=...
# DATABRICKS_TOKEN=...
# OPENAI_API_KEY=sk-...
```

### 4. Run It!
```bash
python main.py "Which products have the highest adoption?"
```

---

## Example Output

```
================================================================================
Question: Which products have the highest adoption?
================================================================================

Table Analysis:
  Relevant tables: product_adoption

Generated SQL:
SELECT product_name, adoption_rate, active_users
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

---

## Test Questions

```bash
# Easy: Single table
python main.py "Which products have the highest adoption?"

# Medium: Join two tables
python main.py "Which products have high usage but also high support demand?"

# Hard: Multiple conditions
python main.py "Show me products with adoption above 70% and less than 50 support requests per month"
```

---

## Key Files to Read

1. **ARCHITECTURE.md** — Deep dive into every file and function
2. **README.md** — Full documentation and interview prep
3. **PHASE3_SUMMARY.md** — What was created and why

---

## Interview Talking Points (30 seconds)

> "I built a LangGraph-based SQL data agent. Users ask business questions in natural language. The agent:
>
> 1. Understands the question and identifies relevant tables
> 2. Uses OpenAI (gpt-4o-mini) to generate SQL from the question
> 3. Validates SQL for safety (SELECT-only, approved tables only)
> 4. Executes on Databricks SQL warehouse
> 5. Returns business-friendly results
>
> LangGraph handles the orchestration. The state flows through 5 nodes: analyze → generate → validate → [retry if needed] → execute → answer. Conditional routing means invalid SQL gets retried instead of blindly executed.
>
> Key security: Three validation layers (prompt, validation check, executor check). LLM only sees approved tables and columns."

---

## Troubleshooting

**Config Error: Missing DATABRICKS_HOST**
→ Check .env file exists and has all required variables

**OPENAI_API_KEY error**
→ Ensure OPENAI_API_KEY=sk-... is in .env

**Databricks connection refused**
→ Verify DATABRICKS_HOST is correct (get from Databricks UI)

**Column X not found**
→ LLM hallucinated a column. Check actual schema in Databricks.

**Query references unapproved table**
→ LLM tried to use a table outside workspace.digital_product. Schema might need refinement.

---

## Next Steps

1. Run a few example questions
2. Try breaking it (use bad questions, test edge cases)
3. Read ARCHITECTURE.md for deep understanding
4. Read README.md for interview prep
5. Consider Phase 4: Add business result interpretation using LLM

