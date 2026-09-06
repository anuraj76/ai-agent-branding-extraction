"""Main entry point for testing the SQL data agent."""

import os
import sys
import ssl

# Load environment variables FIRST before any other imports
from dotenv import load_dotenv
load_dotenv()

# Monkey-patch SSL to accept self-signed certificates
# This is needed for corporate networks or self-signed certificates
_original_create_default_context = ssl.create_default_context

def _patched_create_default_context(*args, **kwargs):
    ctx = _original_create_default_context(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

ssl.create_default_context = _patched_create_default_context

# Also set environment variables
os.environ['DATABRICKS_DISABLE_VERIFY_SSL'] = 'true'

from src.support_agent.agent import SQLDataAgent


def print_result(result: dict) -> None:
    """Pretty print the agent result."""
    print("\n" + "=" * 80)
    print(f"Question: {result['question']}")
    print("=" * 80)

    if result["table_analysis"]:
        print(f"\nTable Analysis:\n  {result['table_analysis']}")

    if result["sql_query"]:
        print(f"\nGenerated SQL:\n{result['sql_query']}")

    if result["validation_error"]:
        print(f"\nValidation Error:\n  {result['validation_error']}")
    else:
        print(f"\nValidation: ✓ PASSED")

    if result["sql_error"]:
        print(f"\nExecution Error:\n  {result['sql_error']}")

    if result["retry_count"] > 0:
        print(f"\nRetries: {result['retry_count']}")

    print(f"\nFinal Answer:\n{result['final_answer']}")
    print("=" * 80 + "\n")


def main():
    """Run the agent with a test question."""

    # Example questions to try
    questions = [
        "Which products have the highest adoption?",
        "Which products have high usage but also high support demand?",
        "Which customers are most engaged?",
    ]

    try:
        print("DEBUG: Starting initialization...", flush=True)
        print("Initializing SQL Data Agent...", flush=True)
        print("DEBUG: About to create SQLDataAgent...", flush=True)
        agent = SQLDataAgent()
        print("DEBUG: SQLDataAgent created", flush=True)
        print("✓ Agent initialized successfully\n")

        # Run with first question or custom input
        if len(sys.argv) > 1:
            question = " ".join(sys.argv[1:])
        else:
            question = questions[0]

        print(f"Running agent with question: {question}\n", flush=True)
        print("DEBUG: About to call agent.run()...", flush=True)
        result = agent.run(question)
        print("DEBUG: agent.run() returned", flush=True)
        print_result(result)

    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("\nMake sure to set these environment variables:")
        print("  DATABRICKS_HOST")
        print("  DATABRICKS_HTTP_PATH")
        print("  DATABRICKS_TOKEN")
        print("\nSee .env.example for details")
        sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
