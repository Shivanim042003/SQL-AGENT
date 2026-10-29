"""
Database-role check: the last line of defence.

Connects with READONLY_DATABASE_URL (the role the agent uses) and tries
statements that must NOT work. Every attempt runs inside a transaction that
is always rolled back, and the statements are written to change nothing even
if the role were misconfigured. Prints PASS when the database refuses.

Run from the project root:   python eval/run_db_role_check.py
"""

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import psycopg2  # noqa: E402

import config  # noqa: E402

# (label, sql, expected outcome: refused as 'permission'/'timeout', or a
# query that must return False)
ATTEMPTS = [
    ("delete rows", "DELETE FROM users WHERE false", "permission"),
    ("update rows", "UPDATE users SET age = age WHERE false", "permission"),
    ("insert row", "INSERT INTO users (id) SELECT 1 WHERE false", "permission"),
    ("truncate", "TRUNCATE TABLE users", "permission"),
    ("drop table", "DROP TABLE users", "permission"),
    ("alter table", "ALTER TABLE users ADD COLUMN zz int", "permission"),
    ("create table", "CREATE TABLE zz_probe (a int)", "permission"),
    ("select into", "SELECT * INTO zz_probe FROM users WHERE false", "permission"),
    # GRANT by a non-owner only raises a warning, so check the role itself.
    ("role is not privileged",
     "SELECT rolsuper OR rolcreatedb OR rolcreaterole "
     "FROM pg_roles WHERE rolname = current_user", "false"),
    ("role can delete users",
     "SELECT has_table_privilege(current_user, 'users', "
     "'DELETE,UPDATE,INSERT,TRUNCATE')", "false"),
    ("read a file", "SELECT pg_read_file('/etc/passwd')", "permission"),
    ("list a directory", "SELECT pg_ls_dir('/')", "permission"),
    ("copy to program", "COPY users TO PROGRAM 'true'", "permission"),
    ("other schema table",
     "SELECT * FROM document_embeddings LIMIT 1", "permission"),
    ("long sleep", "SELECT pg_sleep(30)", "timeout"),
]


def attempt(sql):
    conn = psycopg2.connect(config.READONLY_DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '15s'")
        cur.execute(sql)
        row = cur.fetchone() if cur.description else None
        if row is not None and row[0] is False:
            return "false", "returned False"
        return "ALLOWED", ""
    except psycopg2.errors.QueryCanceled as exc:
        return "timeout", str(exc).strip().splitlines()[0]
    except psycopg2.errors.InsufficientPrivilege as exc:
        return "permission", str(exc).strip().splitlines()[0]
    except psycopg2.Error as exc:
        return "error", str(exc).strip().splitlines()[0]
    finally:
        conn.rollback()  # never keep anything
        conn.close()


def main():
    if not config.READONLY_DATABASE_URL:
        sys.exit("READONLY_DATABASE_URL is not set.")

    failures = 0
    print(f"{'attempt':<22}{'result':<12}detail")

    for label, sql, expected in ATTEMPTS:
        started = time.perf_counter()
        result, detail = attempt(sql)
        took = time.perf_counter() - started

        passed = result == expected
        failures += not passed
        print(
            f"{label:<22}{result:<12}{detail[:60]} ({took:.1f}s) "
            f"{'PASS' if passed else 'FAIL'}"
        )

    print(f"\n{len(ATTEMPTS) - failures}/{len(ATTEMPTS)} refused as expected.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
