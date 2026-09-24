from schema_metadata import ALL_TABLES, Column, TableSchema
import os
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
load_dotenv()
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
INDEX_NAME = "medquery-schema"
EMBED_DIM = 384
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
    model = SentenceTransformer(EMBED_MODEL_NAME)
    docs = build_all_documents()
    table_docs = sum(1 for d in docs if d["metadata"]["level"] == "table")
    column_docs = sum(1 for d in docs if d["metadata"]["level"] == "column")
    print(f"  {table_docs} table-level docs, {column_docs} column-level docs, {len(docs)} total.")
    
    texts = [d["text"] for d in docs]
    print("Embedding documents locally...")
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
    vectors=[{"id":doc["id"],
              "values":embedding.tolist(),
              "metadata":{**doc["metadata"], "text": doc["text"]}} for doc,embedding in zip(docs, embeddings)]
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