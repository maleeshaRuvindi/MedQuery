"""
eval/run_ragas_eval.py

Runs RAGAS scoring (faithfulness, context_precision, answer_relevancy) over the
results produced by run_pipeline.py.

IMPORTANT — SEPARATE VIRTUAL ENVIRONMENT REQUIRED:
  RAGAS's installed version currently depends on an older langchain-core (<1.0),
  while your agent.py/tools.py depend on the current langgraph/langchain-groq
  stack (langchain-core >=1.4). These two requirements conflict in a single
  environment. This script is therefore designed to run in its OWN venv, separate
  from the one running agent.py / run_pipeline.py.

SETUP (run once):
    python3 -m venv .venv-ragas
    source .venv-ragas/bin/activate        # Windows: .venv-ragas\\Scripts\\activate
    pip install ragas langchain-groq python-dotenv

USAGE (every time you want to score a fresh pipeline run):
    1. In your MAIN venv:   python eval/run_pipeline.py        (writes pipeline_results.json)
    2. In the RAGAS venv:   python eval/run_ragas_eval.py      (reads it, writes scores)

Judge LLM: Groq (openai/gpt-oss-120b) — reused per your choice, no OpenAI key needed.
Judge embeddings: RAGAS's context_precision metric also needs an embedding model
internally (separate from your retrieval embedder) — we reuse the same free local
sentence-transformers model for this, so no second cost/dependency is introduced.
"""

import json
import os

from dotenv import load_dotenv
from datasets import Dataset

from ragas import evaluate
from ragas.metrics import faithfulness, context_precision, answer_relevancy
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

INPUT_PATH = os.path.join("eval", "pipeline_results.json")
OUTPUT_PATH = os.path.join("eval", "ragas_scores.json")


def load_dataset() -> Dataset:
    if not os.path.exists(INPUT_PATH):
        raise RuntimeError(f"{INPUT_PATH} not found. Run eval/run_pipeline.py first (in your main venv).")

    with open(INPUT_PATH) as f:
        results = json.load(f)

    # RAGAS expects specific column names: question, answer, contexts, ground_truth
    dataset_dict = {
        "question": [r["question"] for r in results],
        "answer": [r["answer"] for r in results],
        "contexts": [r["contexts"] for r in results],  # list[list[str]] — RAGAS wants contexts per-row as a list
        "ground_truth": [r["ground_truth"] for r in results],
    }

    # Guard against rows that will silently produce NaN scores: empty answer or empty contexts.
    # We keep them in the dataset (so the report shows the failure) but flag them clearly.
    for i, (ans, ctx) in enumerate(zip(dataset_dict["answer"], dataset_dict["contexts"])):
        if not ans:
            print(f"WARNING: row {i} ({results[i]['id']}) has an empty answer — scores for this row will be unreliable.")
        if not ctx:
            print(f"WARNING: row {i} ({results[i]['id']}) has zero contexts — context_precision will be unreliable.")

    return Dataset.from_dict(dataset_dict), results


def main():
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        raise RuntimeError("GROQ_API_KEY not set — required for RAGAS's judge LLM.")

    print("Loading dataset from pipeline results...")
    dataset, raw_results = load_dataset()

    print("Setting up Groq as the RAGAS judge LLM (openai/gpt-oss-120b)...")
    judge_llm = LangchainLLMWrapper(ChatGroq(model="openai/gpt-oss-120b", temperature=0))

    print("Setting up local sentence-transformers as the RAGAS judge embedder...")
    # Reuses the same free, local embedding approach as your retrieval pipeline —
    # no second paid dependency introduced just for evaluation.
    judge_embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )

    print(f"Running RAGAS evaluation over {len(dataset)} rows (this calls the judge LLM multiple times per row)...")
    result = evaluate(
        dataset,
        metrics=[faithfulness, context_precision, answer_relevancy],
        llm=judge_llm,
        embeddings=judge_embeddings,
    )

    scores_df = result.to_pandas()

    # Attach the question id back on, for readability when you inspect per-row scores.
    scores_df.insert(0, "id", [r["id"] for r in raw_results])

    print("\n=== Per-question scores ===")
    print(scores_df[["id", "question", "faithfulness", "context_precision", "answer_relevancy"]].to_string(index=False))

    print("\n=== Aggregate scores (mean across all questions) ===")
    aggregate = {
        "faithfulness": float(scores_df["faithfulness"].mean()),
        "context_precision": float(scores_df["context_precision"].mean()),
        "answer_relevancy": float(scores_df["answer_relevancy"].mean()),
    }
    for metric, value in aggregate.items():
        print(f"  {metric}: {value:.4f}")

    scores_df.to_json(OUTPUT_PATH, orient="records", indent=2)
    print(f"\nFull per-question results written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
