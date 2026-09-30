import sqlite3
import pandas as pd
import os
DATABASE_PATH = os.path.join("data", "mimic.db")
conn = sqlite3.connect(DATABASE_PATH)
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Tables:", cursor.fetchall())

# Quick check each table
for table in ["patients", "admissions", "diagnoses_icd"]:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    print(f"{table}: {cursor.fetchone()[0]} rows")


# df1 = pd.read_sql("SELECT * FROM patients LIMIT 1", conn)
# df2 = pd.read_sql("SELECT * FROM admissions LIMIT 1", conn)
# df3 = pd.read_sql("SELECT * FROM diagnoses_icd LIMIT 1", conn)
# print("...column names.......")
# print(df1.columns.tolist())
# print(df2.columns.tolist())
# print(df3.columns.tolist())
for table in ["patients", "admissions", "diagnoses_icd"]:
    print(f"\n=== {table} ===")
    cursor.execute(f"PRAGMA table_info({table})")
    for row in cursor.fetchall():
        # row = (cid, name, type, notnull, default, pk)
        print(f"  {row[1]:<30} {row[2]}")
conn.close()