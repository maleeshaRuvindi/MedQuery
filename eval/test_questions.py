"""
eval/test_questions.py

18 test questions for RAGAS evaluation, spanning:
  - narrow tables (patients, admissions, diagnoses_icd, procedures_icd)
  - wide tables (labevents, chartevents, prescriptions) via their dict tables
  - a mix of simple lookups, aggregations, joins, and time-filtered queries
  - 2 deliberately "should fail gracefully" cases (asks about data NOT in the schema)

Each entry has a `reference_sql` query that WE believe correctly answers the question.
generate_ground_truth.py runs each reference_sql against your real data/mimic.db and
fills in `ground_truth` with the actual resulting answer text — that's what makes this
Approach 1 (exact ground truth) rather than Approach 2 (pattern-based).

IMPORTANT: review reference_sql yourself before running generate_ground_truth.py —
these are MY best guess at correct queries given schema_metadata.py, but you know the
real MIMIC-IV schema and your actual loaded data better than I do. If a query looks
wrong for your data, fix it here before generating ground truth from it.
"""

TEST_QUESTIONS = [
    # --- Narrow tables: patients ---
    {
        "id": "q01",
        "question": "What is the gender distribution of patients?",
        "reference_sql": "SELECT gender, COUNT(*) AS count FROM patients GROUP BY gender;",
    },
    {
        "id": "q02",
        "question": "What is the average age of patients?",
        "reference_sql": "SELECT AVG(anchor_age) AS avg_age FROM patients;",
    },
    {
        "id": "q03",
        "question": "How many patients have died (have a date of death recorded)?",
        "reference_sql": "SELECT COUNT(*) AS deceased_count FROM patients WHERE dod IS NOT NULL;",
    },

    # --- Narrow tables: admissions ---
    {
        "id": "q04",
        "question": "How many hospital admissions were emergency admissions?",
        "reference_sql": "SELECT COUNT(*) AS emergency_count FROM admissions WHERE admission_type LIKE '%EMER%';",
    },
    {
        "id": "q05",
        "question": "What is the breakdown of admissions by insurance type?",
        "reference_sql": "SELECT insurance, COUNT(*) AS count FROM admissions GROUP BY insurance ORDER BY count DESC;",
    },
    {
        "id": "q06",
        "question": "How many patients died during their hospital admission?",
        "reference_sql": "SELECT COUNT(*) AS in_hospital_deaths FROM admissions WHERE hospital_expire_flag = 1;",
    },
    {
        "id": "q07",
        "question": "What is the average length of stay in days for hospital admissions?",
        "reference_sql": (
            "SELECT AVG(julianday(dischtime) - julianday(admittime)) AS avg_los_days "
            "FROM admissions WHERE dischtime IS NOT NULL AND admittime IS NOT NULL;"
        ),
    },

    # --- Joins: patients + admissions ---
    {
        "id": "q08",
        "question": "What is the average age of patients admitted as an emergency?",
        "reference_sql": (
            "SELECT AVG(p.anchor_age) AS avg_age FROM patients p "
            "JOIN admissions a ON p.subject_id = a.subject_id "
            "WHERE a.admission_type LIKE '%EMER%';"
        ),
    },

    # --- diagnoses_icd ---
    {
        "id": "q09",
        "question": "What are the 5 most frequently recorded diagnosis codes?",
        "reference_sql": (
            "SELECT icd_code, COUNT(*) AS frequency FROM diagnoses_icd "
            "GROUP BY icd_code ORDER BY frequency DESC LIMIT 5;"
        ),
    },
    {
        "id": "q10",
        "question": "How many distinct patients have at least one recorded diagnosis?",
        "reference_sql": "SELECT COUNT(DISTINCT subject_id) AS patients_with_diagnosis FROM diagnoses_icd;",
    },

    # --- procedures_icd ---
    # {
    #     "id": "q11",
    #     "question": "How many procedures were recorded in total?",
    #     "reference_sql": "SELECT COUNT(*) AS total_procedures FROM procedures_icd;",
    # },

    # # --- Wide table: labevents + d_labitems (requires join to dict table) ---
    # {
    #     "id": "q12",
    #     "question": "How many potassium lab tests were recorded?",
    #     "reference_sql": (
    #         "SELECT COUNT(*) AS potassium_test_count FROM labevents le "
    #         "JOIN d_labitems dl ON le.itemid = dl.itemid "
    #         "WHERE dl.label LIKE '%Potassium%';"
    #     ),
    # },
    # {
    #     "id": "q13",
    #     "question": "How many lab results were flagged as abnormal?",
    #     "reference_sql": "SELECT COUNT(*) AS abnormal_count FROM labevents WHERE flag = 'abnormal';",
    # },
    # {
    #     "id": "q14",
    #     "question": "What is the average creatinine value recorded across all lab events?",
    #     "reference_sql": (
    #         "SELECT AVG(le.valuenum) AS avg_creatinine FROM labevents le "
    #         "JOIN d_labitems dl ON le.itemid = dl.itemid "
    #         "WHERE dl.label LIKE '%Creatinine%' AND le.valuenum IS NOT NULL;"
    #     ),
    # },

    # # --- Wide table: chartevents + d_items ---
    # {
    #     "id": "q15",
    #     "question": "What is the average heart rate recorded in the ICU?",
    #     "reference_sql": (
    #         "SELECT AVG(ce.valuenum) AS avg_heart_rate FROM chartevents ce "
    #         "JOIN d_items di ON ce.itemid = di.itemid "
    #         "WHERE di.label LIKE '%Heart Rate%' AND ce.valuenum IS NOT NULL;"
    #     ),
    # },

    # # --- prescriptions ---
    # {
    #     "id": "q16",
    #     "question": "What are the 5 most commonly prescribed medications?",
    #     "reference_sql": (
    #         "SELECT drug, COUNT(*) AS prescription_count FROM prescriptions "
    #         "GROUP BY drug ORDER BY prescription_count DESC LIMIT 5;"
    #     ),
    # },
    # {
    #     "id": "q17",
    #     "question": "How many prescriptions were administered intravenously (IV)?",
    #     "reference_sql": "SELECT COUNT(*) AS iv_count FROM prescriptions WHERE route = 'IV';",
    # },

    # --- Deliberate edge case: question NOT answerable from current schema ---
    {
        "id": "q18",
        "question": "What is the average BMI of patients in the ICU?",
        "reference_sql": None,  # No height/weight table exists in schema_metadata.py yet —
        # this question SHOULD cause the agent to say "cannot be answered from available tables,"
        # not hallucinate a BMI calculation. ground_truth is written by hand below, not generated.
        "ground_truth_override": (
            "This question cannot be answered with the currently available tables, since no "
            "table containing patient height or weight measurements is defined in the schema."
        ),
    },
]
