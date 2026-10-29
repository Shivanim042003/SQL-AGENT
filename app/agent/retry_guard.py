"""
Helpers that stop retries from repeating the same failed SQL.

The retry prompt already contains the database error, but the model often
resends the identical query. These helpers (1) detect that, and (2) turn
common errors into concrete hints: where a missing column actually lives,
and how to avoid a timeout.
"""

import re


def normalize_sql(sql) -> str:
    return " ".join((sql or "").lower().strip().rstrip(";").split())


def is_repeat(new_sql, previous_sql) -> bool:
    return bool(new_sql) and normalize_sql(new_sql) == normalize_sql(previous_sql)


def tables_with_column(column: str, schema: str) -> list[str]:
    """Schema lines look like 'table: col (type), col (type)'."""

    found = []

    for line in (schema or "").splitlines():

        if ":" not in line:
            continue

        table, _, columns = line.partition(":")
        names = {c.strip().split(" ")[0] for c in columns.split(",")}

        if column in names:
            found.append(table.strip())

    return found


def build_retry_hints(critique: str, schema: str) -> str:
    """Concrete, error-specific advice. Empty when nothing applies."""

    hints = []
    text = critique or ""

    for match in re.finditer(r'column "?(?:\w+\.)?(\w+)"? does not exist', text):

        column = match.group(1)
        tables = tables_with_column(column, schema)

        if tables:
            hints.append(
                f"The column {column} does not exist in the table you used. "
                f"It exists only in: {', '.join(tables)}. Join that table, "
                f"or use the equivalent column of the table you already have."
            )
        else:
            hints.append(
                f"No table has a column named {column}. Pick a real column "
                f"from the schema."
            )

    if "statement timeout" in text.lower():
        hints.append(
            "The previous query was too slow. Do not use correlated "
            "subqueries; use a JOIN with GROUP BY, or aggregate first and "
            "join the result."
        )

    return "\n".join(hints)
