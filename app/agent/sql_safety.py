"""
Second safety layer: a static check on generated SQL before it runs.

The database role (SELECT-only, 15 s timeout) is the real protection; this
layer stops obviously unsafe SQL earlier and gives the retry loop a clear
reason. It works on a "cleaned" copy of the SQL in which comments and the
contents of string literals are removed, so disguises such as
``DELETE/**/FROM`` or ``DELETE`` followed by a newline are still seen, and
harmless text such as ``WHERE note = 'please update'`` is not flagged.
"""

import re

# Whole words that must never appear in a read-only query.
FORBIDDEN_WORDS = (
    "insert", "update", "delete", "drop", "alter", "truncate", "create",
    "grant", "revoke", "copy", "merge", "call", "execute", "vacuum",
    "reindex", "cluster", "refresh", "comment", "lock", "listen", "notify",
    "into",  # SELECT ... INTO creates a table
)

# Functions that read files, sleep, change settings or reach other servers.
FORBIDDEN_FUNCTIONS = (
    "pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir",
    "pg_stat_file", "lo_import", "lo_export", "dblink", "set_config",
    "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf",
    "pg_advisory_lock", "nextval", "setval",
)

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"--[^\n]*")
_STRING = re.compile(r"'(?:[^']|'')*'")
_QUOTED_IDENT = re.compile(r'"(?:[^"]|"")*"')


def clean_sql(sql: str) -> str:
    """Lower-case SQL with comments and quoted text blanked out."""

    text = _BLOCK_COMMENT.sub(" ", sql)
    text = _LINE_COMMENT.sub(" ", text)
    text = _STRING.sub("''", text)
    text = _QUOTED_IDENT.sub('""', text)
    return text.lower()


def check_sql_safety(sql: str) -> str | None:
    """
    Return None if the SQL looks like one safe read-only query, otherwise a
    short reason. Messages match the ones the generator already used.
    """

    cleaned = clean_sql(sql).strip()

    if ";" in cleaned:
        return "Generated SQL contains multiple statements."

    if not re.match(r"(select|with|\()", cleaned):
        return "Generated SQL is not a SELECT query."

    for word in FORBIDDEN_WORDS:
        if re.search(rf"\b{word}\b", cleaned):
            return f"Generated SQL contains a prohibited keyword: {word}"

    for name in FORBIDDEN_FUNCTIONS:
        if re.search(rf"\b{name}\b", cleaned):
            return f"Generated SQL calls a prohibited function: {name}"

    return None
