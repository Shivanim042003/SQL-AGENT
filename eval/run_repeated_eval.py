"""
Repeated-trial evaluation.

Runs every golden question N times through the same pipeline and the same
pass/fail logic as eval/run_golden_eval.py, then reports pass rate, retries and
latency (p50 / p90) per question and overall.

    python eval/run_repeated_eval.py --trials 5
    python eval/run_repeated_eval.py --trials 1 --only medium_03,safety_01
    python eval/run_repeated_eval.py --trials 5 --json results.json
"""

import argparse
import contextlib
import io
import json
import math
import os
import sys
import time
from collections import Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import config
from eval.golden_questions import GOLDEN_QUESTIONS
from eval.run_golden_eval import get_category, run_question


def percentile(values, p):
    ordered = sorted(values)
    index = max(0, math.ceil(p / 100 * len(ordered)) - 1)
    return ordered[index]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--only", default="", help="comma-separated question ids")
    parser.add_argument("--json", default="", help="write raw records to this file")
    args = parser.parse_args()

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    questions = [q for q in GOLDEN_QUESTIONS if not only or q["id"] in only]
    if not questions:
        sys.exit("No matching questions.")

    records = {q["id"]: [] for q in questions}

    for trial in range(args.trials):
        for q in questions:
            started = time.perf_counter()
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    out = run_question(q)
                passed = bool(out["passed"])
                status = out["status"]
                retries = out["result"].get("retry_count", 0) or 0
            except Exception as exc:
                passed, status, retries = False, f"ERROR - {type(exc).__name__}: {exc}", 0
            records[q["id"]].append(
                {
                    "trial": trial + 1,
                    "passed": passed,
                    "status": status,
                    "retries": retries,
                    "seconds": time.perf_counter() - started,
                }
            )
        print(f"trial {trial + 1}/{args.trials} done", file=sys.stderr, flush=True)

    print()
    print("=" * 100)
    print("REPEATED EVALUATION")
    print("=" * 100)
    print(f"trials per question : {args.trials}")
    print(f"model               : {config.LLM_MODEL}  (intent: {config.INTENT_MODEL})")
    print(f"critic shortcuts    : {'on' if config.SKIP_CRITIC_FOR_SIMPLE_COUNTS else 'off'}")
    print(f"OLLAMA_NUM_PARALLEL : {os.getenv('OLLAMA_NUM_PARALLEL', '(not set in this shell)')}")
    print()
    print(f"{'id':<11}{'passed':>8}{'avg retries':>13}{'p50 s':>8}{'p90 s':>8}   failures")
    print("-" * 100)

    all_runs = []
    by_category = {}
    for q in questions:
        runs = records[q["id"]]
        all_runs.extend(runs)
        category = get_category(q["id"])
        by_category.setdefault(category, []).extend(runs)

        passed = sum(r["passed"] for r in runs)
        seconds = [r["seconds"] for r in runs]
        avg_retries = sum(r["retries"] for r in runs) / len(runs)
        failures = Counter(r["status"] for r in runs if not r["passed"])
        failure_text = "; ".join(f"{n}x {s}" for s, n in failures.items())
        print(
            f"{q['id']:<11}{f'{passed}/{len(runs)}':>8}{avg_retries:>13.2f}"
            f"{percentile(seconds, 50):>8.1f}{percentile(seconds, 90):>8.1f}   {failure_text}"
        )

    print("-" * 100)
    print()
    for category, runs in by_category.items():
        passed = sum(r["passed"] for r in runs)
        print(f"{category:<8} {passed}/{len(runs)} passed ({100 * passed / len(runs):.0f}%)")

    total_passed = sum(r["passed"] for r in all_runs)
    print(f"{'overall':<8} {total_passed}/{len(all_runs)} passed ({100 * total_passed / len(all_runs):.0f}%)")

    answered = [r["seconds"] for c, rs in by_category.items() if c != "safety" for r in rs]
    if answered:
        print(
            f"answered-question latency (non-safety): "
            f"p50 {percentile(answered, 50):.1f}s, p90 {percentile(answered, 90):.1f}s"
        )

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(records, handle, indent=2)
        print(f"raw records written to {args.json}")


if __name__ == "__main__":
    main()