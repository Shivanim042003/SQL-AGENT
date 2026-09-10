import os
import sys


# ------------------------------------------------------------
# Allow imports from project root
# ------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)


# ------------------------------------------------------------
# Imports
# ------------------------------------------------------------

from app.agent.intent_node import check_intent
from app.agent.schema_node import load_schema
from app.agent.retrieval_node import retrieve_context
from app.agent.sql_generator import generate_sql
from app.agent.executor_node import execute_sql
from app.agent.critic_node import critique_sql


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

# Initial attempt + 2 retries = maximum 3 attempts
MAX_ATTEMPTS = 3


# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------

def print_line():
    print("=" * 80)


def print_attempt_header(attempt: int):
    print()
    print_line()
    print(f"SQL ATTEMPT {attempt}")
    print_line()


# ------------------------------------------------------------
# Main Pipeline
# ------------------------------------------------------------

def main():

    print_line()
    print("SQL GENERATION + EXECUTION + CRITIC RETRY TEST")
    print_line()

    # --------------------------------------------------------
    # Initial Agent State
    # --------------------------------------------------------

    state = {
        "question": "What is the conversion rate?",

        "schema": "",

        "retrieved_context": "",

        "sql": None,

        "previous_sql": None,

        "query_result": None,

        "error": None,

        "sql_valid": False,

        "critique": "",

        "is_destructive": False,

        "retry_count": 0,

        "final_answer": None
    }

    # --------------------------------------------------------
    # STEP 1: SAFETY CHECK
    # --------------------------------------------------------

    print()
    print("SAFETY CHECK...")

    state.update(check_intent(state))

    print("Is destructive:", state["is_destructive"])

    if state["is_destructive"]:

        print()
        print("STOPPING PIPELINE.")
        print("Destructive requests are not allowed.")

        return

    # --------------------------------------------------------
    # STEP 2: LOAD DATABASE SCHEMA
    # --------------------------------------------------------

    print()
    print("LOADING SCHEMA...")

    state.update(load_schema(state))

    if not state.get("schema"):

        print()
        print("ERROR: Schema could not be loaded.")

        return

    print("Schema loaded successfully.")

    # --------------------------------------------------------
    # STEP 3: RETRIEVE BUSINESS CONTEXT
    # --------------------------------------------------------

    print()
    print("RETRIEVING BUSINESS CONTEXT...")

    state.update(retrieve_context(state))

    print("Business context retrieved successfully.")

    # --------------------------------------------------------
    # STEP 4: SQL GENERATION + EXECUTION + CRITIC LOOP
    # --------------------------------------------------------

    for attempt in range(1, MAX_ATTEMPTS + 1):

        print_attempt_header(attempt)

        # ----------------------------------------------------
        # GENERATE SQL
        # ----------------------------------------------------

        if attempt == 1:

            print()
            print("GENERATING SQL...")

        else:

            print()
            print("REGENERATING SQL USING PREVIOUS SQL + CRITIQUE...")

            print()
            print("-" * 80)
            print("RETRY INFORMATION")
            print("-" * 80)

            print()
            print("PREVIOUS SQL:")
            print(state.get("previous_sql"))

            print()
            print("CRITIQUE:")
            print(state.get("critique"))

        # ----------------------------------------------------
        # Reset execution-specific state
        #
        # IMPORTANT:
        # Do NOT clear previous_sql or critique.
        # They are required by the retry generator.
        # ----------------------------------------------------

        state["sql"] = None
        state["query_result"] = None
        state["error"] = None
        state["sql_valid"] = False

        # ----------------------------------------------------
        # Generate SQL
        # ----------------------------------------------------

        generation_result = generate_sql(state)

        state.update(generation_result)

        # ----------------------------------------------------
        # Handle generation failure
        # ----------------------------------------------------

        if state.get("error"):

            print()
            print("SQL GENERATION ERROR:")
            print(state["error"])

            return

        if not state.get("sql"):

            print()
            print("ERROR: No SQL was generated.")

            return

        print()
        print("GENERATED SQL:")
        print()
        print(state["sql"])

        # ----------------------------------------------------
        # EXECUTE SQL
        # ----------------------------------------------------

        print()
        print("-" * 80)
        print("EXECUTING SQL...")
        print("-" * 80)

        execution_result = execute_sql(state)

        state.update(execution_result)

        if state.get("error"):

            print()
            print("EXECUTION ERROR:")
            print(state["error"])

        else:

            print()
            print("EXECUTION SUCCESSFUL.")

            print()
            print("QUERY RESULT:")
            print(state["query_result"])

        # ----------------------------------------------------
        # CRITIC REVIEW
        # ----------------------------------------------------

        print()
        print("-" * 80)
        print("CRITIC REVIEW...")
        print("-" * 80)

        critic_result = critique_sql(state)

        state.update(critic_result)

        print()
        print("VALID:")
        print(state["sql_valid"])

        print()
        print("CRITIQUE:")
        print(state["critique"])

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if state["sql_valid"] and not state.get("error"):

            print()
            print_line()
            print("PIPELINE SUCCESSFUL")
            print_line()

            print()
            print("QUESTION:")
            print(state["question"])

            print()
            print("FINAL SQL:")
            print(state["sql"])

            print()
            print("FINAL RESULT:")
            print(state["query_result"])

            return

        # ----------------------------------------------------
        # PREPARE RETRY
        # ----------------------------------------------------

        if attempt < MAX_ATTEMPTS:

            # Save current SQL before the next attempt
            # overwrites state["sql"].
            state["previous_sql"] = state["sql"]

            # Increment retry count for diagnostics.
            state["retry_count"] = attempt

            print()
            print_line()
            print("SQL ATTEMPT REJECTED - PREPARING RETRY")
            print_line()

            print()
            print("PREVIOUS SQL SAVED FOR RETRY:")
            print(state["previous_sql"])

            print()
            print("CRITIQUE SAVED FOR RETRY:")
            print(state["critique"])

        # ----------------------------------------------------
        # MAXIMUM ATTEMPTS REACHED
        # ----------------------------------------------------

        else:

            print()
            print_line()
            print("PIPELINE FAILED AFTER MAXIMUM ATTEMPTS")
            print_line()

            print()
            print("LAST SQL:")
            print(state["sql"])

            print()
            print("LAST EXECUTION RESULT:")
            print(state["query_result"])

            print()
            print("LAST EXECUTION ERROR:")
            print(state["error"])

            print()
            print("FINAL CRITIQUE:")
            print(state["critique"])

            print()
            print("RETRY COUNT:")
            print(state["retry_count"])

            return


# ------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------

if __name__ == "__main__":
    main()