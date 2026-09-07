import os
import sys


# ============================================================
# ALLOW IMPORTS FROM PROJECT ROOT
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# IMPORTS
# ============================================================

from app.agent.graph import agent_graph


# ============================================================
# CONFIGURATION
# ============================================================

QUESTION = "What is the conversion rate?"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def print_line():
    print("=" * 80)


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    print_line()
    print("LANGGRAPH SQL AGENT TEST")
    print_line()

    print()
    print("QUESTION:")
    print(QUESTION)

    print()
    print("RUNNING AGENT GRAPH...")
    print()

    # --------------------------------------------------------
    # INITIAL STATE
    # --------------------------------------------------------

    initial_state = {
        # User input
        "question": QUESTION,

        # Safety
        "is_destructive": False,

        # Database grounding
        "schema": "",
        "retrieved_context": "",

        # SQL generation
        "sql": None,
        "previous_sql": None,

        # SQL execution
        "query_result": None,
        "error": None,

        # Critic
        "sql_valid": False,
        "critique": "",

        # Retry control
        "retry_count": 0,

        # Final response
        "final_answer": None,
    }

    # --------------------------------------------------------
    # RUN GRAPH
    # --------------------------------------------------------

    result = agent_graph.invoke(initial_state)

    # --------------------------------------------------------
    # FINAL STATE
    # --------------------------------------------------------

    print()
    print_line()
    print("FINAL STATE")
    print_line()

    print()
    print("QUESTION:")
    print(result.get("question"))

    # --------------------------------------------------------
    # SAFETY
    # --------------------------------------------------------

    print()
    print("IS DESTRUCTIVE:")
    print(result.get("is_destructive"))

    # --------------------------------------------------------
    # SQL
    # --------------------------------------------------------

    print()
    print("FINAL SQL:")
    print(result.get("sql"))

    # --------------------------------------------------------
    # QUERY RESULT
    # --------------------------------------------------------

    print()
    print("QUERY RESULT:")
    print(result.get("query_result"))

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    print()
    print("ERROR:")
    print(result.get("error"))

    # --------------------------------------------------------
    # CRITIC
    # --------------------------------------------------------

    print()
    print("SQL VALID:")
    print(result.get("sql_valid"))

    print()
    print("CRITIQUE:")
    print(result.get("critique"))

    # --------------------------------------------------------
    # RETRY INFORMATION
    # --------------------------------------------------------

    print()
    print("RETRY COUNT:")
    print(result.get("retry_count"))

    print()
    print("PREVIOUS SQL:")
    print(result.get("previous_sql"))

    # --------------------------------------------------------
    # FINAL ANSWER
    # --------------------------------------------------------

    print()
    print_line()
    print("FINAL ANSWER")
    print_line()

    print()
    print(result.get("final_answer"))

    # --------------------------------------------------------
    # PIPELINE STATUS
    # --------------------------------------------------------

    print()
    print_line()

    if result.get("is_destructive"):

        print("PIPELINE STOPPED: DESTRUCTIVE REQUEST")

    elif result.get("sql_valid") and not result.get("error"):

        print("PIPELINE SUCCESSFUL")

    else:

        print("PIPELINE FINISHED WITHOUT A VALID SQL RESULT")

    print_line()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()