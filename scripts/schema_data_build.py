import duckdb
from pathlib import Path
import json

conn = duckdb.connect()
conn.execute("INSTALL sqlite")
conn.execute("LOAD sqlite")

data_dir = Path('D:/ML/MedQuery/data/mimic-iv-clinical-database-demo-2.2/hosp')
sqlite_path = Path('D:/ML/MedQuery/data/mimic_hosp.db')
files = list(data_dir.glob('*.gz')) 
all_schemas = {}
conn.execute(f"ATTACH '{sqlite_path}' AS mimic (TYPE SQLITE)")
for file in files:
    print(f"\n--- Schema for: {file} ---")
    table_name=Path(file.stem).stem
    df = conn.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{file}')").df()
    all_schemas[table_name] = df[['column_name', 'column_type']].to_dict(orient='records')

    # Drop if already exists (safe to re-run)
    conn.execute(f"DROP TABLE IF EXISTS mimic.{table_name}")

    # Write directly from .csv.gz → SQLite table (no pandas in between)
    conn.execute(f"""
        CREATE TABLE mimic.{table_name} AS
        SELECT * FROM read_csv_auto('{file}')
    """)

    print(f"✓ {table_name}")
with open('schemas.json', 'w') as f:
    json.dump(all_schemas, f, indent=2)

conn.execute("DETACH mimic")
print("\nDone. Tables written:", list(all_schemas.keys()))