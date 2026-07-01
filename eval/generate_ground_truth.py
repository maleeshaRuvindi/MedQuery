"""
eval/generate_ground_truth.py

Run this ONCE against your populated data/mimic.db to turn each reference_sql query
in test_questions.py into an exact ground_truth answer string.

This is what makes our RAGAS setup "Approach 1" (exact ground truth from real data)
rather than "Approach 2" (vague pattern-based ground truth) — see the chat discussion
for why that distinction matters specifically for the context_precision metric.

Output: eval/test_questions_with_ground_truth.json
  This file is what the actual RAGAS evaluation script reads from — test_questions.py
  itself is never imported directly by the evaluation, only by this generator.

USAGE:
    python eval/generate_ground_truth.py

If a reference_sql is None (like q18, the deliberate "unanswerable" case), this script
uses the question's ground_truth_override text instead of running anything.
"""

import json
import os
import sqlite3
import sys

# Allow running this script directly (python eval/generate_ground_truth.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.test_questions import TEST_QUESTIONS

DB_PATH = os.path.join("data", "mimic.db")
OUTPUT_PATH = os.path.join("eval", "test_questions_with_ground_truth.json")


def format_result_as_text(question: str, columns: list[str], rows: list[tuple]) -> str:
    """
    Turns a raw SQL result into a plain-English ground truth sentence.
    This is intentionally simple/templated rather than calling an LLM —
    ground truth should be a deterministic, auditable fact, not another
    AI-generated guess (that would defeat the purpose of "ground truth").
    """
    if not rows:
        return "No matching records were found in the database for this query."

    # Single row, single column -> simple scalar answer (e.g. AVG, COUNT)
    if len(rows) == 1 and len(columns) == 1:
        value = rows[0][0]
        if value is None:
            return "No matching records were found in the database for this query."
        if isinstance(value, float):
            value = round(value, 2)
        return f"The result is {value} ({columns[0]})."

    # Single row, multiple columns -> describe each field
    if len(rows) == 1:
        parts = [f"{col}: {val}" for col, val in zip(columns, rows[0])]
        return "The result is " + ", ".join(parts) + "."

    # Multiple rows -> list each row's values, capped to keep ground truth readable
    max_rows_to_describe = 10
    lines = []
    for row in rows[:max_rows_to_describe]:
        parts = [f"{col}={val}" for col, val in zip(columns, row)]
        lines.append("(" + ", ".join(parts) + ")")
    suffix = "" if len(rows) <= max_rows_to_describe else f" ...and {len(rows) - max_rows_to_describe} more rows."
    return f"The results are: {'; '.join(lines)}{suffix}"


def main():
    if not os.path.exists(DB_PATH):
        raise RuntimeError(
            f"Database not found at {DB_PATH}. This script must run against your real, "
            "populated mimic.db — update DB_PATH if your file lives elsewhere."
        )

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    enriched = []
    for item in TEST_QUESTIONS:
        entry = {"id": item["id"], "question": item["question"], "reference_sql": item.get("reference_sql")}

        if item.get("reference_sql") is None:
            # Deliberate "unanswerable" case — use the hand-written override, run nothing.
            entry["ground_truth"] = item["ground_truth_override"]
            entry["sql_executed"] = False
            print(f"[{item['id']}] SKIPPED execution (no reference_sql) -> using override text")
        else:
            try:
                cursor.execute(item["reference_sql"])
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                ground_truth = format_result_as_text(item["question"], columns, rows)
                entry["ground_truth"] = ground_truth
                entry["sql_executed"] = True
                print(f"[{item['id']}] OK -> {ground_truth[:100]}")
            except sqlite3.Error as e:
                # Don't silently skip a broken reference query — surface it so you can
                # fix the SQL in test_questions.py before relying on this ground truth.
                entry["ground_truth"] = None
                entry["sql_executed"] = False
                entry["error"] = str(e)
                print(f"[{item['id']}] SQL ERROR: {e}  <-- fix reference_sql in test_questions.py")

        enriched.append(entry)

    conn.close()

    failed = [e for e in enriched if e["ground_truth"] is None]
    if failed:
        print(f"\n{len(failed)} question(s) failed to execute. Fix their reference_sql and re-run before evaluating.")
    else:
        print(f"\nAll {len(enriched)} questions have ground truth. Writing to {OUTPUT_PATH}...")
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            json.dump(enriched, f, indent=2)
        print("Done.")


if __name__ == "__main__":
    main()
