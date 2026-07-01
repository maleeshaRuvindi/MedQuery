"""
tools.py

Three tools exposed to the agent:

  1. search_schema(query)      -> NEW. Semantic search over Pinecone for relevant
                                   tables/columns given a natural-language question.
                                   This is the discovery step that replaces "the LLM
                                   must already know table names exist."
  2. get_schema(table_names)   -> Same contract as your original tool, but now reads
                                   from schema_metadata.py instead of a hardcoded dict
                                   buried in this file. Called AFTER search_schema, with
                                   exact table names.
  3. execute_sql(query)        -> Unchanged from your original.

Why two separate tools instead of one merged tool:
  - search_schema returns *candidates* ranked by semantic similarity — it's a hint,
    not ground truth, and might occasionally surface a less relevant table for an
    ambiguous question.
  - get_schema returns the *exact, authoritative* column list for table names the LLM
    has now decided to commit to. Keeping them separate means a bad semantic match
    can't silently corrupt the SQL the LLM writes — get_schema always returns ground
    truth for whatever name was actually requested, and clearly errors on typos/
    nonexistent tables instead of guessing.
"""

import os
import json
import sqlite3
from functools import lru_cache

import pandas as pd
from dotenv import load_dotenv
from langchain_core.tools import tool
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone

from schema_metadata import TABLES_BY_NAME

load_dotenv()

DB_PATH = os.path.join("data", "mimic.db")
INDEX_NAME = "medquery-schema"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# Lazy singletons — the embedding model and Pinecone connection are expensive
# to set up, so we build them once and cache, not on every tool call.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_embedder() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL_NAME)


@lru_cache(maxsize=1)
def _get_pinecone_index():
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY not set — required for search_schema.")
    pc = Pinecone(api_key=api_key)
    return pc.Index(INDEX_NAME)


# ---------------------------------------------------------------------------
# Tool 1: search_schema — semantic discovery over the full MIMIC-IV schema
# ---------------------------------------------------------------------------

@tool
def search_schema(query: str, top_k: int = 5) -> str:
    """
    Semantically search the full MIMIC-IV schema to find which tables (and, for
    wide tables, which specific columns) are relevant to a natural-language question.

    ALWAYS call this FIRST, before get_schema, especially when you are not certain
    which exact table names exist. Pass the user's question (or your interpretation
    of what data is needed) as the query — not a guessed table name.

    Returns a ranked list of candidate tables/columns with similarity scores and
    descriptions. Use the returned table names as input to get_schema to confirm
    exact column definitions before writing SQL.
    """
    embedder = _get_embedder()

    index = _get_pinecone_index()
    print(index._config.host)
    query_vector = embedder.encode([query], normalize_embeddings=True)[0].tolist()

    results = index.query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True,
    )

    if not results.get("matches"):
        return "No matching tables found. Try rephrasing the query with different clinical terms."

    # Group hits by table so the LLM gets a clean "here are the relevant tables,
    # and here's WHY (which columns matched)" view instead of a flat dump.
    by_table: dict[str, dict] = {}
    for match in results["matches"]:
        meta = match["metadata"]
        table = meta["table"]
        by_table.setdefault(table, {"score": match["score"], "table_desc": None, "matched_columns": []})

        if meta["level"] == "table":
            by_table[table]["table_desc"] = meta["text"]
            by_table[table]["score"] = max(by_table[table]["score"], match["score"])
        else:
            by_table[table]["matched_columns"].append(
                {"column": meta["column"], "score": round(match["score"], 4), "text": meta["text"]}
            )

    # Sort tables by best score descending
    ranked = sorted(by_table.items(), key=lambda kv: kv[1]["score"], reverse=True)

    output = []
    for table_name, info in ranked:
        entry = {
            "table": table_name,
            "relevance_score": round(info["score"], 4),
            "description": info["table_desc"] or f"(no table-level doc found for {table_name})",
        }
        if info["matched_columns"]:
            entry["matched_columns"] = info["matched_columns"]
        output.append(entry)

    return json.dumps({"candidates": output}, indent=2)


# ---------------------------------------------------------------------------
# Tool 2: get_schema — exact, authoritative column lookup
# ---------------------------------------------------------------------------

@tool
def get_schema(table_names: list[str]) -> str:
    """
    Returns exact column names and types for the requested MIMIC tables.
    Call this AFTER search_schema has identified candidate table names, and
    BEFORE writing any SQL query, to confirm exact column names exist.
    """
    result = []
    for name in table_names:
        table = TABLES_BY_NAME.get(name)
        if table is None:
            result.append(f"Table `{name}`: not found. Use search_schema to find the correct table name.")
            continue
        cols = ", ".join(f"{c.name} ({c.dtype})" for c in table.columns)
        result.append(f"Table `{table.name}`: {cols}\n  Notes: {table.join_hints}")

    return "\n".join(result)


# ---------------------------------------------------------------------------
# Tool 3: execute_sql — unchanged from original
# ---------------------------------------------------------------------------

def is_safe_query(query: str) -> bool:
    forbidden = ["drop", "delete", "insert", "update", "alter", "truncate"]
    query_lower = query.lower().strip()
    return not any(word in query_lower for word in forbidden)


@tool
def execute_sql(query: str) -> str:
    """
    Execute a read-only SQL query against the MIMIC database.
    Returns columns, row count, and up to 20 rows of results.
    Always call get_schema first to ensure correct column names.
    """
    if not is_safe_query(query):
        return "Error: Only SELECT queries are permitted."

    if "limit" not in query.lower():
        query = query.rstrip(";") + " LIMIT 100;"

    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(query, conn)

        if df.empty:
            return json.dumps({
                "row_count": 0,
                "message": "No results returned. The query may be too restrictive or reference wrong values.",
            })

        return json.dumps({
            "row_count": len(df),
            "columns": list(df.columns),
            "data": df.head(20).to_dict(orient="records"),
        }, indent=2, default=str)

    except Exception as e:
        return f"SQL Error: {str(e)}\nCheck column names using get_schema and try again."
    finally:
        conn.close()


TOOLS = [search_schema, get_schema, execute_sql]