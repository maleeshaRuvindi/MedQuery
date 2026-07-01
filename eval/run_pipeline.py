"""
eval/run_pipeline.py

Runs the ClinIQ agent once per test question and collects exactly what RAGAS needs:
  - question     : the input question
  - answer       : the agent's final natural-language response
  - contexts     : list[str] of "retrieved" content -> Option B (per user's choice):
                    search_schema tool outputs + execute_sql tool outputs
  - ground_truth : pulled from eval/test_questions_with_ground_truth.json
                    (must run generate_ground_truth.py first)

WHY contexts = search_schema + execute_sql outputs (Option B), not just search_schema:
  RAGAS's faithfulness metric checks whether the final answer's CLAIMS are supported
  by the context. A claim like "142 male patients" can only be verified against the
  actual SQL execution result — schema docs alone never contain that number. Without
  execute_sql output in contexts, faithfulness would have nothing to check numeric
  claims against, and would silently under-detect hallucination.

NOTE: get_schema tool output is intentionally excluded from contexts. get_schema
returns exact/authoritative column definitions (ground truth itself, not retrieved
knowledge from a vector store or the database) — including it would conflate "the
schema I already know" with "the contexts I retrieved", which is the wrong shape
for these metrics.

USAGE:
    python eval/generate_ground_truth.py     # run first, once per data/schema change
    python eval/run_pipeline.py               # run this every time you want fresh eval data

Output: eval/pipeline_results.json
  Consumed by eval/run_ragas_eval.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import ToolMessage

from db_query_agent import graph, SYSTEM_PROMPT

GROUND_TRUTH_PATH = os.path.join("eval", "test_questions_with_ground_truth.json")
OUTPUT_PATH = os.path.join("eval", "pipeline_results.json")

# Tool names whose output counts as "retrieved context" for RAGAS (Option B).
CONTEXT_TOOL_NAMES = {"search_schema", "execute_sql"}


def extract_final_answer(messages: list) -> str:
    """
    The final AIMessage in the run is the agent's answer to the user. We walk
    backwards and return the first AIMessage content we find that ISN'T empty
    (an AIMessage can have empty content when it's purely a tool-call step).
    """
    for msg in reversed(messages):
        if type(msg).__name__ == "AIMessage" and msg.content:
            return msg.content
    return ""


def extract_contexts(messages: list) -> list[str]:
    """
    Walks the full message history and pulls .content from every ToolMessage
    produced by search_schema or execute_sql (Option B). Order is preserved
    (search_schema calls typically happen before execute_sql in the agent's
    workflow, but we don't enforce that here — we just collect what happened).
    """
    contexts = []
    for msg in messages:
        if isinstance(msg, ToolMessage) and msg.name in CONTEXT_TOOL_NAMES:
            contexts.append(msg.content)
    return contexts


def run_single_question(question: str) -> dict:
    """Invokes the LangGraph agent for one question, returns {answer, contexts}."""
    response = graph.invoke(
        {"messages": [SYSTEM_PROMPT, {"role": "user", "content": question}]},
        config={"recursion_limit": 15},
    )
    messages = response["messages"]
    return {
        "answer": extract_final_answer(messages),
        "contexts": extract_contexts(messages),
        "num_messages": len(messages),  # useful for debugging stuck/looping runs
    }


def main():
    if not os.path.exists(GROUND_TRUTH_PATH):
        raise RuntimeError(
            f"{GROUND_TRUTH_PATH} not found. Run `python eval/generate_ground_truth.py` first."
        )

    with open(GROUND_TRUTH_PATH) as f:
        questions = json.load(f)

    results = []
    for i, item in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] Running: {item['question'][:80]}")
        try:
            run_output = run_single_question(item["question"])
        except Exception as e:
            print(f"  ERROR running pipeline: {e}")
            run_output = {"answer": "", "contexts": [], "num_messages": 0, "error": str(e)}

        results.append({
            "id": item["id"],
            "question": item["question"],
            "answer": run_output["answer"],
            "contexts": run_output["contexts"],
            "ground_truth": item["ground_truth"],
        })

        n_ctx = len(run_output["contexts"])
        ans_preview = (run_output["answer"][:80] + "...") if run_output["answer"] else "(empty answer!)"
        print(f"  -> {n_ctx} context(s) retrieved, answer: {ans_preview}")

    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    empty_answers = sum(1 for r in results if not r["answer"])
    empty_contexts = sum(1 for r in results if not r["contexts"])
    print(f"\nDone. Wrote {len(results)} results to {OUTPUT_PATH}")
    if empty_answers:
        print(f"WARNING: {empty_answers} question(s) produced an empty answer — check agent logs for those.")
    if empty_contexts:
        print(f"WARNING: {empty_contexts} question(s) produced zero contexts — search_schema/execute_sql may not have been called.")


if __name__ == "__main__":
    main()
