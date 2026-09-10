import os
import sys
import psycopg2

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)

import config

conn = psycopg2.connect(config.READONLY_DATABASE_URL)
cur = conn.cursor()

cur.execute("SET statement_timeout = '15s';")

sql = """
SELECT
    COUNT(DISTINCT CASE
        WHEN event_type = 'purchase' THEN session_id
    END) * 100.0
    /
    COUNT(DISTINCT session_id)
    AS conversion_rate
FROM events;
"""

try:
    cur.execute(sql)

    print(cur.fetchall())

except Exception as e:
    print("ERROR:", e)

finally:
    cur.close()
    conn.close()