"""
Helpers for the ablation evaluation (no database or model needed).

* results_match(): compares the agent's rows with the reference rows.
* summarize(): turns per-question records into the headline numbers.

An answer is judged correct only by comparing its rows with the rows of a
hand-written reference query run on the same database. No model's opinion
(including the critic's) is used to decide correctness.
"""

import itertools
import math
import statistics
from datetime import date, datetime
from decimal import Decimal

REL_TOL = 1e-4
ABS_TOL = 0.011  # tolerates 2-decimal rounding


# ============================================================
# VALUE / ROW NORMALIZATION
# ============================================================

def _norm(value):
    """Reduce a database value to a number, string or None."""

    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _to_rows(result):
    """Accept rows as dicts (agent) or tuples/lists (reference)."""

    rows = []
    for row in result or []:
        if isinstance(row, dict):
            row = list(row.values())
        rows.append(tuple(_norm(v) for v in row))
    return rows


def _sort_key(row):
    # None < numbers < strings; numbers rounded so tiny float noise
    # cannot reorder rows.
    key = []
    for v in row:
        if v is None:
            key.append((0, 0.0, ""))
        elif isinstance(v, float):
            key.append((1, round(v, 2), ""))
        else:
            key.append((2, 0.0, v))
    return tuple(key)


def _values_equal(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    return a == b


def _rows_equal(rows_a, rows_b, ordered):
    if len(rows_a) != len(rows_b):
        return False
    if not ordered:
        rows_a = sorted(rows_a, key=_sort_key)
        rows_b = sorted(rows_b, key=_sort_key)
    for ra, rb in zip(rows_a, rows_b):
        if len(ra) != len(rb):
            return False
        if not all(_values_equal(a, b) for a, b in zip(ra, rb)):
            return False
    return True


# ============================================================
# PUBLIC COMPARATOR
# ============================================================

def results_match(reference, actual, ordered=False, allow_extra_columns=True):
    """
    True when ``actual`` contains the same data as ``reference``.

    * Column names are ignored (the model may alias differently).
    * Row order is ignored unless ``ordered`` is True.
    * Numbers match within a small tolerance.
    * With ``allow_extra_columns`` the agent may return additional columns
      (for example a name next to an id); every reference column must still
      be present, with the same values in the same rows.
    * An empty reference matches only an empty result.
    """

    ref_rows = _to_rows(reference)
    act_rows = _to_rows(actual)

    if len(ref_rows) != len(act_rows):
        return False

    if not ref_rows:
        return True

    ref_width = len(ref_rows[0])
    act_width = len(act_rows[0])

    if act_width < ref_width:
        return False

    if act_width > ref_width and (not allow_extra_columns or act_width > 8):
        return False

    # Try every choice/ordering of the agent's columns that has the
    # reference's width (so column order does not matter either).
    candidates = itertools.permutations(range(act_width), ref_width)

    for columns in candidates:
        projected = [tuple(row[i] for i in columns) for row in act_rows]
        if _rows_equal(ref_rows, projected, ordered):
            return True

    return False


# ============================================================
# SUMMARY
# ============================================================

def _percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


def summarize(records):
    """
    Headline numbers for one configuration.

    Each record needs: first_correct (bool), final_correct (bool),
    answered (bool), latency (seconds), tokens (int), retries (int).
    """

    total = len(records)

    if total == 0:
        return {"questions": 0}

    first = sum(1 for r in records if r["first_correct"])
    final = sum(1 for r in records if r["final_correct"])
    answered = sum(1 for r in records if r["answered"])

    # Wrong answers shown to the user as if verified.
    confident_wrong = sum(
        1 for r in records if r["answered"] and not r["final_correct"]
    )

    fixed = sum(
        1 for r in records if not r["first_correct"] and r["final_correct"]
    )
    broken = sum(
        1 for r in records if r["first_correct"] and not r["final_correct"]
    )

    latencies = [r["latency"] for r in records]
    tokens = [r["tokens"] for r in records]

    return {
        "questions": total,
        "first_attempt_correct": first,
        "final_correct": final,
        "first_attempt_accuracy": first / total,
        "final_accuracy": final / total,
        "answered": answered,
        "confident_wrong": confident_wrong,
        "successful_corrections": fixed,
        "harmful_corrections": broken,
        "total_retries": sum(r["retries"] for r in records),
        "latency_p50": statistics.median(latencies),
        "latency_p90": _percentile(latencies, 90),
        "tokens_mean": statistics.mean(tokens),
        "tokens_total": sum(tokens),
    }


# ============================================================
# OUTCOMES, INTERVALS, CRITIC CONFUSION
# ============================================================

def outcome(record):
    """fixed / broken / right_both / wrong_both (first attempt vs final)."""

    first, final = record["first_correct"], record["final_correct"]

    if first and final:
        return "right_both"
    if first and not final:
        return "broken"
    if final:
        return "fixed"
    return "wrong_both"


def wilson_interval(successes, total, z=1.96):
    """95% Wilson score interval for a proportion (low, high)."""

    if total == 0:
        return (0.0, 0.0)

    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = (
        z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    ) / denom

    return (max(0.0, centre - margin), min(1.0, centre + margin))


def critic_confusion(records):
    """
    How good the critic's verdicts are, judged against the reference.

    Only attempts that executed without error and received a critic verdict
    are counted (execution errors are rejected without asking the critic).
    """

    counts = {
        "accepted_correct": 0,
        "accepted_wrong": 0,
        "rejected_correct": 0,
        "rejected_wrong": 0,
    }

    for record in records:
        for attempt in record.get("attempts", []):
            if attempt.get("error") or attempt.get("critic_valid") is None:
                continue

            verdict = "accepted" if attempt["critic_valid"] else "rejected"
            truth = "correct" if attempt.get("correct") else "wrong"
            counts[f"{verdict}_{truth}"] += 1

    return counts


def paired_change(records_a, records_b):
    """On questions both configs ran: how many got right / wrong going a -> b."""

    by_id_a = {r["id"]: r for r in records_a}
    gained = lost = 0

    for rb in records_b:
        ra = by_id_a.get(rb["id"])
        if ra is None:
            continue
        if rb["final_correct"] and not ra["final_correct"]:
            gained += 1
        if ra["final_correct"] and not rb["final_correct"]:
            lost += 1

    return gained, lost


# ============================================================
# MARKDOWN REPORT
# ============================================================

def _pct(x):
    return f"{100 * x:.1f}%"


def _fmt_rows(rows, limit=3):
    if rows is None:
        return "none"
    text = str(rows[:limit])
    if len(rows) > limit:
        text += f" ... ({len(rows)} rows)"
    return text if len(text) < 200 else text[:197] + "..."


def build_report(records_by_config, config_names, questions_by_id, model_note=""):
    """Render the results as markdown (pure function, easy to test)."""

    lines = ["# Ablation results", ""]

    if model_note:
        lines += [model_note, ""]

    lines += [
        "Correctness is decided by comparing the agent's rows with a "
        "hand-written reference query run on the same database, never by a "
        "model's opinion. Shortcuts (hardcoded SQL and critic rules) are "
        "switched off for every configuration.",
        "",
        "## Headline",
        "",
        "| Config | Questions | First attempt | Final | 95% CI (final) | "
        "Fixed by retry | Broken by retry | Wrong but shown | "
        "Latency p50 / p90 | Tokens / question |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    summaries = {}

    for name in config_names:
        recs = records_by_config.get(name, [])
        if not recs:
            continue
        s = summarize(recs)
        summaries[name] = s
        low, high = wilson_interval(s["final_correct"], s["questions"])
        lines.append(
            f"| {name} | {s['questions']} "
            f"| {s['first_attempt_correct']} ({_pct(s['first_attempt_accuracy'])}) "
            f"| {s['final_correct']} ({_pct(s['final_accuracy'])}) "
            f"| {_pct(low)} to {_pct(high)} "
            f"| {s['successful_corrections']} | {s['harmful_corrections']} "
            f"| {s['confident_wrong']} "
            f"| {s['latency_p50']:.1f}s / {s['latency_p90']:.1f}s "
            f"| {s['tokens_mean']:.0f} |"
        )

    lines += [
        "",
        "*First attempt* = the first SQL the model wrote. *Final* = what the "
        "user would be shown. *Wrong but shown* = answered, but the rows do "
        "not match the reference. Latency includes any rate-limit waits.",
        "",
    ]

    # ---- by category ----
    categories = sorted({q["category"] for q in questions_by_id.values()})
    lines += ["## Final accuracy by category", ""]
    lines.append("| Category | " + " | ".join(config_names) + " |")
    lines.append("|---|" + "---|" * len(config_names))

    for cat in categories:
        cells = []
        for name in config_names:
            recs = [
                r for r in records_by_config.get(name, [])
                if r["category"] == cat
            ]
            if not recs:
                cells.append("-")
                continue
            ok = sum(1 for r in recs if r["final_correct"])
            cells.append(f"{ok}/{len(recs)}")
        lines.append(f"| {cat} | " + " | ".join(cells) + " |")

    lines.append("")

    # ---- paired changes ----
    present = [n for n in config_names if records_by_config.get(n)]
    if len(present) > 1:
        lines += ["## Question-by-question changes (final correctness)", ""]
        for prev, nxt in zip(present, present[1:]):
            gained, lost = paired_change(
                records_by_config[prev], records_by_config[nxt]
            )
            lines.append(
                f"- {prev} -> {nxt}: {gained} questions became correct, "
                f"{lost} became wrong."
            )
        lines.append("")

    # ---- critic quality ----
    for name in present:
        conf = critic_confusion(records_by_config[name])
        if sum(conf.values()) == 0:
            continue
        lines += [
            f"## Critic verdicts in config {name}",
            "",
            "Judged against the reference, on attempts that ran without a "
            "database error.",
            "",
            "| | SQL was correct | SQL was wrong |",
            "|---|---|---|",
            f"| Critic accepted | {conf['accepted_correct']} "
            f"| {conf['accepted_wrong']} (missed errors) |",
            f"| Critic rejected | {conf['rejected_correct']} "
            f"(false alarms) | {conf['rejected_wrong']} |",
            "",
        ]

    # ---- failure traces ----
    lines += ["## Traces", ""]
    interesting = ("fixed", "broken", "wrong_both")

    for name in present:
        traces = [
            r for r in records_by_config[name] if outcome(r) in interesting
        ]
        if not traces:
            continue

        lines += [f"### Config {name}", ""]
        order = {"broken": 0, "fixed": 1, "wrong_both": 2}
        traces.sort(key=lambda r: order[outcome(r)])

        for r in traces[:12]:
            q = questions_by_id.get(r["id"], {})
            lines += [
                f"**{r['id']}** ({outcome(r)}): {r['question']}",
                "",
                f"- Reference SQL: `{q.get('reference_sql', '')}`",
                f"- Reference rows: {_fmt_rows(r.get('reference_rows'))}",
            ]
            for i, a in enumerate(r.get("attempts", [])):
                verdict = a.get("critic_valid")
                verdict = "n/a" if verdict is None else (
                    "accepted" if verdict else "rejected"
                )
                tag = "correct" if a.get("correct") else "wrong"
                err = f" error: {a['error'][:120]}" if a.get("error") else ""
                lines.append(
                    f"- Attempt {i}: {tag}; critic {verdict}{err}  \n"
                    f"  `{(a.get('sql') or '').strip()}`  \n"
                    f"  rows: {_fmt_rows(a.get('rows'))}"
                )
                if a.get("critique"):
                    lines.append(f"  critic said: {a['critique'][:200]}")
            if r.get("crashed"):
                lines.append(f"- Run problem: {r['crashed'][:200]}")
            lines.append("")

    return "\n".join(lines)
