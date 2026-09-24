import pandas as pd
import sqlite3
import os

# ── Config ──────────────────────────────────────────────
HOSP_DIR = os.path.join("data","mimic-iv-clinical-database-demo-2.2","hosp")
DB_PATH = os.path.join("data","mimic.db")

# ── Connect ─────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)

# ── Load tables ─────────────────────────────────────────
tables = {
    "patients":      os.path.join(HOSP_DIR, "patients.csv.gz"),
    "admissions":    os.path.join(HOSP_DIR, "admissions.csv.gz"),
    "diagnoses_icd": os.path.join(HOSP_DIR, "diagnoses_icd.csv.gz"),
}

for table_name, file_path in tables.items():
    print(f"Loading {table_name}...")
    df = pd.read_csv(file_path, compression="gzip")
    print(f"  → {len(df)} rows, columns: {list(df.columns)}")
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    print(f"  ✓ saved to mimic.db")

conn.close()
print("\nDone. mimic.db created.")