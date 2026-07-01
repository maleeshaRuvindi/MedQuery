"""
build_index.py

Run this ONCE (or whenever schema_metadata.py changes) to populate Pinecone with
schema embeddings. This is offline/setup-time work — it does NOT run as part of
the agent's request/response loop.

Embedding model: sentence-transformers/all-MiniLM-L6-v2
  - Runs fully locally on CPU. No API key, no per-call cost, no network dependency
    at query time. 384-dim output — small and fast, plenty for a few dozen short
    technical schema descriptions.

Vector DB: Pinecone (free tier, serverless)
  - Requires a PINECONE_API_KEY in your .env (free signup at pinecone.io).
  - Free tier allows up to 100K vectors / 1 index on the "starter" serverless spec —
    we'll use a small fraction of that.

Document strategy (hybrid granularity):
  - Every table gets ONE table-level doc (id: "table::<name>").
  - Tables flagged `wide=True` ALSO get one doc PER COLUMN (id: "column::<table>::<col>"),
    because for these tables a clinician's question usually maps to a specific
    column/value rather than the table as a whole (e.g. "creatinine" -> labevents.valuenum
    filtered by itemid, not just "the labevents table").
"""

import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec

from schema_metadata import ALL_TABLES, TableSchema, Column

load_dotenv()

INDEX_NAME = "medquery-schema"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_DIM = 384  # matches all-MiniLM-L6-v2 output size


def build_table_doc(table: TableSchema) -> tuple[str, str]:
    """Returns (doc_id, doc_text) for a table-level embedding document."""
    col_summary = ", ".join(c.name for c in table.columns)
    text = (
        f"Table: {table.name} (module: {table.module}). "
        f"{table.description} "
        f"Columns: {col_summary}. "
        f"{table.join_hints}"
    )
    return f"table::{table.name}", text


def build_column_doc(table: TableSchema, column: Column) -> tuple[str, str]:
    """Returns (doc_id, doc_text) for a column-level embedding document (wide tables only)."""
    text = (
        f"Column: {table.name}.{column.name} ({column.dtype}). "
        f"Table context: {table.description} "
        f"{column.description}"
    )
    return f"column::{table.name}::{column.name}", text


def build_all_documents() -> list[dict]:
    """
    Returns a flat list of {id, text, metadata} dicts ready to embed + upsert.
    metadata always carries `table` so retrieval results can be grouped/deduped
    back to table names regardless of whether the hit was a table-doc or column-doc.
    """
    docs = []

    for table in ALL_TABLES:
        doc_id, text = build_table_doc(table)
        docs.append({
            "id": doc_id,
            "text": text,
            "metadata": {"table": table.name, "level": "table", "module": table.module},
        })

        if table.wide:
            for column in table.columns:
                doc_id, text = build_column_doc(table, column)
                docs.append({
                    "id": doc_id,
                    "text": text,
                    "metadata": {
                        "table": table.name,
                        "level": "column",
                        "column": column.name,
                        "module": table.module,
                    },
                })

    return docs


def main():
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "PINECONE_API_KEY not found in environment. "
            "Sign up free at https://www.pinecone.io and add the key to your .env file."
        )

    print(f"Loading local embedding model '{EMBED_MODEL_NAME}' (CPU, first run downloads ~90MB)...")
    model = SentenceTransformer(EMBED_MODEL_NAME)

    print("Building schema documents from schema_metadata.py...")
    docs = build_all_documents()
    table_docs = sum(1 for d in docs if d["metadata"]["level"] == "table")
    column_docs = sum(1 for d in docs if d["metadata"]["level"] == "column")
    print(f"  {table_docs} table-level docs, {column_docs} column-level docs, {len(docs)} total.")

    print("Embedding documents locally...")
    texts = [d["text"] for d in docs]
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    print("Connecting to Pinecone...")
    pc = Pinecone(api_key=api_key)

    existing_indexes = [idx["name"] for idx in pc.list_indexes()]
    if INDEX_NAME not in existing_indexes:
        print(f"Creating Pinecone index '{INDEX_NAME}' (dim={EMBED_DIM}, cosine, free serverless)...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBED_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    else:
        print(f"Index '{INDEX_NAME}' already exists, will upsert into it.")

    index = pc.Index(INDEX_NAME)

    vectors = [
        {
            "id": doc["id"],
            "values": embedding.tolist(),
            "metadata": {**doc["metadata"], "text": doc["text"]},
        }
        for doc, embedding in zip(docs, embeddings)
    ]

    print(f"Upserting {len(vectors)} vectors to Pinecone...")
    # Pinecone recommends batches of ~100 for upsert
    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i : i + batch_size]
        index.upsert(vectors=batch)

    print("Done. Index stats:")
    print(index.describe_index_stats())


if __name__ == "__main__":
    main()