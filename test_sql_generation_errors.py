from app.agent.sql_generator import generate_sql


def base_state():
    return {
        "request_id": "test-request",
        "question": "How many purchase events are there?",
        "is_destructive": False,
        "schema": "events(id, event_type, session_id)",
        "retrieved_context": "",
        "sql": None,
        "previous_sql": None,
        "query_result": None,
        "error": None,
        "error_type": "NONE",
        "sql_valid": False,
        "critique": "",
        "retry_count": 0,
        "final_answer": None,
    }


def main():
    print("\nTesting SQL generation...")
    print("--------------------------------------")

    result = generate_sql(base_state())

    print(f"sql: {result.get('sql')}")
    print(f"error_type: {result.get('error_type')}")
    print(f"error: {result.get('error')}")


if __name__ == "__main__":
    main()