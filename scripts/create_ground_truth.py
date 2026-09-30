import sqlite3
import json
conn=sqlite3.connect("data/mimic_hosp.db")
cursor=conn.cursor()


with open('ground_truth_dataset.json', 'r') as f:
    data=json.load(f)

for i,example in enumerate(data):
    try:
        result=cursor.execute(example["expected_sql"]).fetchall()
        example["sql_result"]=result
    except Exception as e:
        example["sql_result"]=str(e)
with open('ground_truth_dataset.json', 'w') as f:
    json.dump(data,f,indent=2)
# import json

# # Read standard JSON file
# with open('golden_data.json', 'r', encoding='utf-8') as f:
#     data = json.load(f)

# # Write to JSONL file
# with open('golden_dataset.jsonl', 'w', encoding='utf-8') as outfile:
#     for entry in data:
#         outfile.write(json.dumps(entry) + '\n')
