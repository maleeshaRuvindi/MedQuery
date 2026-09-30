import sqlite3
import pandas as pd
import json
from langchain_core.tools import tool
import os
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
from functools import lru_cache
from guardrails import run_sql_guards, scrub_results,check_row_count
from guardrails.exceptions import GuardrailError
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join("data", "mimic_hosp.db")
INDEX_NAME = "medquery-schema"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

@lru_cache(maxsize=1)
def _get_embedder() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL_NAME,cache_folder='/opt/ml/model')


@lru_cache(maxsize=1)
def _get_pinecone_index():
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY not set — required for search_schema.")
    pc = Pinecone(api_key=api_key)
    return pc.Index(INDEX_NAME)

def is_safe_query(query: str) -> bool:
    forbidden = ["drop", "delete", "insert", "update", "alter", "truncate"]
    query_lower = query.lower().strip()
    is_safe = not any(word in query_lower for word in forbidden) and query_lower.startswith("select")
    return is_safe

@tool
def execute_sql(query: str) -> str:
    """
    Execute a read-only SQL query against the MIMIC database.
    Returns columns, row count, and up to 20 rows of results.
    Always call get_schema first to ensure correct column names.
    """
    # SQL guardrail
    try:
        query = run_sql_guards(query)
    except GuardrailError as e:
        return f"Query blocked by safety guardrail: {e.message}"

    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(query, conn)

        if df.empty:
            return json.dumps({
                "row_count": 0,
                "message": "No results returned. The query may be too restrictive."
            })
        try:
            check_row_count(df.to_dict(orient="records"))
        except GuardrailError as e:
            return f"Query blocked by safety guardrail: {e.message}"

        raw_records = df.head(20).to_dict(orient="records")
        safe_records = scrub_results(raw_records)   # output guard
        logger.info(json.dumps({
            "event": "sql_executed",
            "query": query,
            "row_count": len(df)
        }))
        return json.dumps({
            "row_count": len(df),
            "columns": list(df.columns),
            "data": safe_records
        }, indent=2, default=str)

    except Exception as e:
        return f"SQL Error: {str(e)}"
    finally:
        conn.close()
def load_schemas(path='schemas.json'):
    with open(path, 'r') as f:
        return json.load(f)
@tool
def get_schema(table_names: list[str]) -> str:
    """
    Returns exact column names and types for the requested MIMIC tables.
    Call this BEFORE writing any SQL query, to confirm exact column names exist.
    """
    all_schemas=load_schemas()
    ddl = ""
    for table in table_names:
        if table in all_schemas:
            ddl += f"CREATE TABLE {table} (\n"
            col_lines = [
                f"    {col['column_name']}  {col['column_type']}"
                for col in all_schemas[table]
            ]
            ddl += ",\n".join(col_lines)
            ddl += "\n);\n\n"
    return ddl

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
TOOLS = [get_schema, execute_sql]