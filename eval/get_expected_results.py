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

import psycopg2
import config


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    """Create a connection to the project database."""

    return psycopg2.connect(config.DATABASE_URL)


# ============================================================
# HELPER FUNCTION
# ============================================================

def run_query(cursor, query):
    """Execute a query and return the result."""

    cursor.execute(query)
    return cursor.fetchall()


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("GENERATING EXPECTED RESULTS FOR GOLDEN QUESTIONS")
    print("=" * 80)

    connection = None
    cursor = None

    try:

        # ----------------------------------------------------
        # CONNECT TO DATABASE
        # ----------------------------------------------------

        connection = get_connection()
        cursor = connection.cursor()

        print()
        print("Connected to database successfully.")
        print()

        # ====================================================
        # EASY_01
        # ====================================================

        print("-" * 80)
        print("easy_01 - How many events are there?")
        print("-" * 80)

        result = run_query(
            cursor,
            """
            SELECT COUNT(*)
            FROM events;
            """
        )

        print("Expected result:", result)

        # ====================================================
        # EASY_02
        # ====================================================

        print()
        print("-" * 80)
        print("easy_02 - How many distinct sessions are there?")
        print("-" * 80)

        result = run_query(
            cursor,
            """
            SELECT COUNT(DISTINCT session_id)
            FROM events;
            """
        )

        print("Expected result:", result)

        # ====================================================
        # EASY_03
        # ====================================================

        print()
        print("-" * 80)
        print("easy_03 - How many purchase events are there?")
        print("-" * 80)

        result = run_query(
            cursor,
            """
            SELECT COUNT(*)
            FROM events
            WHERE event_type = 'purchase';
            """
        )

        print("Expected result:", result)

        # ====================================================
        # MEDIUM_01
        # ====================================================

        print()
        print("-" * 80)
        print("medium_01 - How many events occurred for each event type?")
        print("-" * 80)

        result = run_query(
            cursor,
            """
            SELECT
                event_type,
                COUNT(*) AS event_count
            FROM events
            GROUP BY event_type
            ORDER BY event_type;
            """
        )

        print("Expected result:")

        for row in result:
            print(row)

        # ====================================================
        # MEDIUM_02
        # ====================================================

        print()
        print("-" * 80)
        print("medium_02 - Which event type occurs most frequently?")
        print("-" * 80)

        result = run_query(
            cursor,
            """
            SELECT
                event_type,
                COUNT(*) AS event_count
            FROM events
            GROUP BY event_type
            ORDER BY event_count DESC
            LIMIT 1;
            """
        )

        print("Expected result:", result)

        # ====================================================
        # MEDIUM_03
        # ====================================================

        print()
        print("-" * 80)
        print("medium_03 - How many sessions contain a purchase event?")
        print("-" * 80)

        result = run_query(
            cursor,
            """
            SELECT COUNT(DISTINCT session_id)
            FROM events
            WHERE event_type = 'purchase';
            """
        )

        print("Expected result:", result)

        # ====================================================
        # HARD_01
        # ====================================================

        print()
        print("-" * 80)
        print("hard_01 - What is the conversion rate?")
        print("-" * 80)

        result = run_query(
            cursor,
            """
            SELECT
                (
                    COUNT(DISTINCT CASE
                        WHEN event_type = 'purchase'
                        THEN session_id
                    END)
                    * 100.0
                    /
                    COUNT(DISTINCT session_id)
                ) AS conversion_rate
            FROM events;
            """
        )

        print("Expected result:", result)

        # ====================================================
        # COMPLETE
        # ====================================================

        print()
        print("=" * 80)
        print("EXPECTED RESULT GENERATION COMPLETE")
        print("=" * 80)

    except Exception as error:

        print()
        print("=" * 80)
        print("ERROR")
        print("=" * 80)

        print(error)

    finally:

        # ----------------------------------------------------
        # CLEANUP
        # ----------------------------------------------------

        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

        print()
        print("Database connection closed.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()