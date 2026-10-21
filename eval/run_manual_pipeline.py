import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from app.agent.intent_node import check_intent
from app.agent.schema_node import load_schema
from app.agent.retrieval_node import retrieve_context
from app.agent.sql_generator import generate_sql
from app.agent.executor_node import execute_sql


QUESTION = "What is the conversion rate?"


def main():

    state = {
        "question": QUESTION,
        "is_destructive": False,
        "schema": "",
        "retrieved_context": "",
        "sql": None,
        "query_result": None,
        "error": None,
        "final_answer": None,
    }

    print("=" * 80)
    print("MANUAL END-TO-END AGENT PIPELINE TEST")
    print("=" * 80)

    print("\nQUESTION:")
    print(state["question"])

    # ------------------------------------------------------------
    # 1. Intent / Safety Check
    # ------------------------------------------------------------

    print("\n" + "=" * 80)
    print("STEP 1: SAFETY CHECK")
    print("=" * 80)

    state.update(check_intent(state))

    print("Is destructive:")
    print(state["is_destructive"])

    if state["is_destructive"]:
        print("\nStopping: destructive request detected.")
        return

    # ------------------------------------------------------------
    # 2. Schema
    # ------------------------------------------------------------

    print("\n" + "=" * 80)
    print("STEP 2: SCHEMA")
    print("=" * 80)

    state.update(load_schema(state))

    print("Schema loaded:", bool(state["schema"]))

    # ------------------------------------------------------------
    # 3. Retrieval
    # ------------------------------------------------------------

    print("\n" + "=" * 80)
    print("STEP 3: RETRIEVAL")
    print("=" * 80)

    state.update(retrieve_context(state))

    print(state["retrieved_context"])

    # ------------------------------------------------------------
    # 4. SQL Generation
    # ------------------------------------------------------------

    print("\n" + "=" * 80)
    print("STEP 4: SQL GENERATION")
    print("=" * 80)

    state.update(generate_sql(state))

    if state["error"]:
        print("SQL generation error:")
        print(state["error"])
        return

    print("Generated SQL:")
    print(state["sql"])

    # ------------------------------------------------------------
    # 5. SQL Execution
    # ------------------------------------------------------------

    print("\n" + "=" * 80)
    print("STEP 5: SQL EXECUTION")
    print("=" * 80)

    state.update(execute_sql(state))

    if state["error"]:
        print("Execution error:")
        print(state["error"])
        return

    print("Query result:")
    print(state["query_result"])

    # ------------------------------------------------------------
    # Final summary
    # ------------------------------------------------------------

    print("\n" + "=" * 80)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 80)

    print("\nQUESTION:")
    print(state["question"])

    print("\nSQL:")
    print(state["sql"])

    print("\nRESULT:")
    print(state["query_result"])


if __name__ == "__main__":
    main()