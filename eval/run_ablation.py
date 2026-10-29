"""
Held-out ablation evaluation.

Compares configurations of the same agent on questions that are not in the
golden or red-team sets, judging every answer against a reference query:

    A  generation only         (no glossary retrieval, no critic, no retries)
    B  + retrieval             (glossary context, still no critic or retries)
    C  + critic and retries    (the full pipeline, up to 2 retries)
    D  critic and retries without retrieval (optional, to separate the effects)

Hardcoded shortcuts (fixed SQL for known questions, fixed critic rules) are
switched off for all of them, so every number comes from the model.

Usage (from the project root):

    python eval/run_ablation.py --validate-reference     # check the references only
    python eval/run_ablation.py --limit 5                # small trial
    python eval/run_ablation.py                          # A, B and C on all questions
    python eval/run_ablation.py --report-only            # rebuild REPORT.md

Runs resume: a (config, question) pair already in records.jsonl is skipped
(unless the earlier attempt crashed, for example on a rate limit).
"""

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from decimal import Decimal

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# When run as a script these must be set before config and the agent modules
# are imported. (Not done on plain import, so tests are unaffected.)
if __name__ == "__main__":
    os.environ["DISABLE_SHORTCUTS"] = "1"
    os.environ["SKIP_CRITIC_FOR_SIMPLE_COUNTS"] = "0"

import psycopg2  # noqa: E402

import config  # noqa: E402
from app.agent.graph import build_graph  # noqa: E402
from app.llm import usage  # noqa: E402
from eval.ablation_lib import build_report, results_match  # noqa: E402
if os.getenv("ABLATION_SET") == "heldout":
    from eval.heldout_questions import QUESTIONS  # noqa: E402
    _SET_DIR = "heldout"
else:
    from eval.ablation_questions import QUESTIONS  # noqa: E402
    _SET_DIR = "ablation"

# name -> (use_retrieval, use_critic, max_retries, description)
CONFIGS = {
    "A": (False, False, 0, "generation only"),
    "B": (True, False, 0, "generation + retrieval"),
    "C": (True, True, 2, "retrieval + critic + retries"),
    "D": (False, True, 2, "critic + retries, no retrieval"),
}

OUT_DIR = os.path.join(PROJECT_ROOT, "eval", "results", _SET_DIR)
RECORDS = os.path.join(OUT_DIR, "records.jsonl")
REFERENCE = os.path.join(OUT_DIR, "reference.json")
REPORT = os.path.join(OUT_DIR, "REPORT.md")

ROW_LIMIT = 20  # rows kept per result in the records file


# ============================================================
# REFERENCE QUERIES
# ============================================================

def _json_default(value):
    """Keep numbers as numbers in the cache (Decimal -> float)."""

    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def run_reference(sql):
    """Run a reference query with the owner connection."""

    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '120s'")
        cur.execute(sql)
        return [list(row) for row in cur.fetchall()]
    finally:
        conn.close()


def load_references(questions, force=False):
    """Run (or load cached) reference results. Fails loudly on any error."""

    cache = {}
    if os.path.exists(REFERENCE) and not force:
        with open(REFERENCE, encoding="utf-8") as fh:
            cache = json.load(fh)

    problems = []

    for q in questions:
        if q["id"] in cache and cache[q["id"]]["sql"] == q["reference_sql"]:
            continue
        try:
            rows = run_reference(q["reference_sql"])
        except Exception as exc:  # noqa: BLE001
            problems.append((q["id"], str(exc).strip().splitlines()[0]))
            continue
        cache[q["id"]] = {
            "sql": q["reference_sql"],
            "rows": json.loads(json.dumps(rows, default=_json_default)),
        }

    if problems:
        print("\nREFERENCE QUERIES FAILED - fix these before evaluating:")
        for qid, msg in problems:
            print(f"  {qid}: {msg}")
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(REFERENCE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, indent=1)

    return cache


def is_trivially_empty(rows):
    return not rows or all(
        v in (None, 0, 0.0, "0") for row in rows for v in row
    )


def validate_references(questions):
    refs = load_references(questions, force=True)
    suspicious = 0

    print(f"\n{'id':<12}{'rows':>6}  first row")
    for q in questions:
        rows = refs[q["id"]]["rows"]
        flag = ""
        empty = is_trivially_empty(rows)
        if q.get("expect_empty") and not empty:
            flag = "  <-- expected empty/zero but has data"
        if not q.get("expect_empty") and empty:
            flag = "  <-- unexpectedly empty/zero"
        if flag:
            suspicious += 1
        print(f"{q['id']:<12}{len(rows):>6}  {str(rows[:1])[:70]}{flag}")

    print(
        f"\n{len(questions)} reference queries ran. "
        f"{suspicious} look suspicious (see arrows above)."
    )


# ============================================================
# RUNNING ONE QUESTION
# ============================================================

def initial_state(question):
    return {
        "request_id": str(uuid.uuid4()),
        "question": question,
        "is_destructive": False,
        "schema": "",
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


def trim(rows):
    if rows is None:
        return None
    return json.loads(json.dumps(rows[:ROW_LIMIT], default=str))


def run_question(graph, q, reference_rows, has_critic=True):
    """Run one question and return a record (never raises)."""

    ordered = bool(q.get("ordered"))
    state = {}
    attempts = []
    crashed = None

    usage_before = usage.snapshot()
    started = time.perf_counter()

    try:
        for chunk in graph.stream(
            initial_state(q["question"]), stream_mode="updates"
        ):
            for node, update in chunk.items():
                if not update:
                    continue
                state.update(update)

                if node == "execute_sql":
                    rows = state.get("query_result")
                    error = state.get("error")
                    attempts.append({
                        "sql": state.get("sql"),
                        "error": error,
                        "rows": trim(rows),
                        "correct": bool(
                            not error
                            and rows is not None
                            and results_match(
                                reference_rows, rows, ordered=ordered
                            )
                        ),
                    })
                elif node == "critique_sql" and attempts and has_critic:
                    attempts[-1]["critic_valid"] = update.get("sql_valid")
                    attempts[-1]["critique"] = update.get("critique", "")
    except Exception as exc:  # noqa: BLE001
        crashed = f"{type(exc).__name__}: {exc}"

    latency = time.perf_counter() - started
    used = usage.delta(usage_before)

    # A model that could not be reached (Ollama stopped, bad key, rate limit)
    # is a problem with the run, not a wrong answer: mark it as crashed so it
    # is retried next time instead of being scored as incorrect.
    if crashed is None and state.get("error_type") == "LLM_ERROR":
        crashed = "LLM error: " + str(
            state.get("error") or state.get("final_answer") or "unknown"
        )

    answered = bool(
        crashed is None
        and state.get("sql_valid")
        and not state.get("error")
        and not state.get("is_destructive")
        and attempts
    )

    # What the user is shown is the last executed attempt, if accepted.
    final_correct = bool(answered and attempts[-1]["correct"])

    return {
        "id": q["id"],
        "category": q["category"],
        "question": q["question"],
        "attempts": attempts,
        "first_correct": bool(attempts and attempts[0]["correct"]),
        "final_correct": final_correct,
        "answered": answered,
        "retries": max(0, len(attempts) - 1),
        "latency": round(latency, 2),
        "tokens": used["prompt_tokens"] + used["completion_tokens"],
        "llm_calls": used["calls"],
        "final_answer": state.get("final_answer"),
        "crashed": crashed,
    }


# ============================================================
# RECORDS FILE
# ============================================================

def read_records():
    records = []
    if os.path.exists(RECORDS):
        with open(RECORDS, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def write_records(records):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(RECORDS, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, default=str) + "\n")


def write_report(records, config_names, refs):
    questions_by_id = {q["id"]: q for q in QUESTIONS}
    by_config = {name: [] for name in config_names}

    for r in records:
        if r["config"] in by_config:
            if r["id"] in refs:
                r = {**r, "reference_rows": refs[r["id"]]["rows"][:ROW_LIMIT]}
            by_config[r["config"]].append(r)

    note = (
        f"Model: `{config.LLM_MODEL}` via `{config.LLM_PROVIDER}`. "
        f"Run on {time.strftime('%Y-%m-%d')}."
    )
    fingerprint = hashlib.sha256(
        json.dumps(
            [(q["id"], q["question"], q["reference_sql"]) for q in QUESTIONS]
        ).encode("utf-8")
    ).hexdigest()[:12]
    text = build_report(
        by_config, config_names, questions_by_id, note, fingerprint
    )

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write(text)

    return text


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--configs", default="A,B,C",
                        help="comma list from A,B,C,D (default A,B,C)")
    parser.add_argument("--limit", type=int, default=0,
                        help="only the first N questions")
    parser.add_argument("--ids", default="", help="comma list of question ids")
    parser.add_argument("--categories", default="",
                        help="comma list: joins,dates,business,empty,aggregation")
    parser.add_argument("--pause", type=float,
                        default=float(os.getenv("EVAL_PAUSE_SECONDS", "0") or 0),
                        help="seconds to wait between questions")
    parser.add_argument("--validate-reference", action="store_true",
                        help="run the reference queries only, then exit")
    parser.add_argument("--report-only", action="store_true",
                        help="rebuild REPORT.md from records.jsonl")
    args = parser.parse_args()

    questions = list(QUESTIONS)
    if args.ids:
        wanted = set(args.ids.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    if args.categories:
        wanted = set(args.categories.split(","))
        questions = [q for q in questions if q["category"] in wanted]
    if args.limit:
        questions = questions[: args.limit]

    config_names = [c.strip().upper() for c in args.configs.split(",") if c.strip()]
    for name in config_names:
        if name not in CONFIGS:
            sys.exit(f"Unknown config {name!r}. Choose from {sorted(CONFIGS)}.")

    if args.validate_reference:
        validate_references(questions)
        return

    refs = load_references(questions)

    if args.report_only:
        write_report(read_records(), config_names, refs)
        print(f"Wrote {REPORT}")
        return

    records = read_records()
    done = {
        (r["config"], r["id"]) for r in records if not r.get("crashed")
    }
    # Drop earlier crashed rows for configs we are about to rerun.
    records = [
        r for r in records
        if not (r.get("crashed") and r["config"] in config_names)
    ]

    for name in config_names:
        use_retrieval, use_critic, max_retries, label = CONFIGS[name]
        graph = build_graph(
            use_retrieval=use_retrieval,
            use_critic=use_critic,
            max_retries=max_retries,
        )
        print(f"\n=== Config {name}: {label} ===")

        for q in questions:
            if (name, q["id"]) in done:
                continue

            record = run_question(
                graph, q, refs[q["id"]]["rows"], has_critic=use_critic
            )
            record["config"] = name
            records.append(record)
            write_records(records)  # save after every question

            status = (
                "CRASHED" if record["crashed"]
                else "correct" if record["final_correct"]
                else "wrong" if record["answered"]
                else "no answer"
            )
            print(
                f"{name} {q['id']:<10} {status:<10} "
                f"first={'ok' if record['first_correct'] else 'no':<3} "
                f"retries={record['retries']} "
                f"{record['latency']:>6.1f}s {record['tokens']:>6} tok"
            )

            if args.pause:
                time.sleep(args.pause)

    write_report(records, config_names, refs)
    print(f"\nWrote {REPORT}")
    crashed = [r for r in records if r.get("crashed")]
    if crashed:
        print(f"{len(crashed)} questions crashed (rerun the same command to retry).")


if __name__ == "__main__":
    main()
