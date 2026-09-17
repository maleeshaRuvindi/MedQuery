import duckdb
from pathlib import Path
import json

conn = duckdb.connect()

data_dir = Path('D:/ML/MedQuery/data/mimic-iv-clinical-database-demo-2.2/hosp')
files = list(data_dir.glob('*.gz')) 
all_schemas = {}

for file in files:
    print(f"\n--- Schema for: {file} ---")
    table_name=Path(file.stem).stem
    df = conn.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{file}')").df()
    all_schemas[table_name] = df[['column_name', 'column_type']].to_dict(orient='records')
    print(f"✓ {table_name}")
with open('schemas.json', 'w') as f:
    json.dump(all_schemas, f, indent=2)

print(all_schemas.keys())