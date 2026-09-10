from app.agent.executor_node import execute_sql


def main():
    print("\nTesting SQL timeout classification...")
    print("--------------------------------------")

    state = {
        "sql": "SELECT pg_sleep(20);",
    }

    result = execute_sql(state)

    print(f"error_type: {result.get('error_type')}")
    print(f"error: {result.get('error')}")


if __name__ == "__main__":
    main()