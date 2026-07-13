from dataclasses import dataclass

@dataclass
class Column:
    name: str
    dtype: str
    description: str = ""

@dataclass
class TableSchema:
    name: str
    module: str
    description: str
    columns: list[Column]
    wide: bool = False
    join_hints: str = ""
PATIENTS = TableSchema(
    name="patients",
    module="hosp",
    description=(
        "Demographic information for every patient: gender, age, and date of death. "
        "One row per patient. Use this table for questions about patient demographics, "
        "gender distribution, age distribution, or mortality (date of death)."
    ),
    join_hints="Join key: subject_id (links to admissions, diagnoses_icd, and all other tables).",
    columns=[
        Column("subject_id", "INTEGER", "Unique patient identifier."),
        Column("gender", "TEXT", "Patient gender: 'M' or 'F'."),
        Column("anchor_age", "INTEGER", "Patient's age at the anchor_year."),
        Column("anchor_year", "INTEGER", "De-identified reference year for this patient."),
        Column("anchor_year_group", "TEXT", "3-year window the anchor_year falls into."),
        Column("dod", "TEXT", "Date of death, if applicable. NULL if patient is alive."),
    ],
)

ADMISSIONS = TableSchema(
    name="admissions",
    module="hosp",
    description=(
        "Hospital admission records: one row per hospital stay. Contains admission/discharge "
        "timestamps, admission type (emergency, elective, urgent), where the patient was admitted "
        "from and discharged to, insurance, marital status, race, language, and in-hospital death flag. "
        "Use this table for questions about length of stay, admission type, mortality during admission, "
        "demographics tied to a specific hospital stay, or insurance/race/marital status breakdowns."
    ),
    join_hints="Join keys: subject_id (links to patients), hadm_id (links to diagnoses_icd, procedures_icd).",
    columns=[
        Column("hadm_id", "INTEGER", "Unique hospital admission identifier."),
        Column("subject_id", "INTEGER", "Patient identifier, links to patients table."),
        Column("admittime", "TEXT", "Timestamp the patient was admitted."),
        Column("dischtime", "TEXT", "Timestamp the patient was discharged."),
        Column("deathtime", "TEXT", "Timestamp of in-hospital death, if applicable."),
        Column("admission_type", "TEXT", "e.g. EW EMER., ELECTIVE, URGENT, OBSERVATION ADMIT."),
        Column("admit_provider_id", "TEXT", "De-identified ID of admitting provider."),
        Column("admission_location", "TEXT", "Where the patient was admitted from."),
        Column("discharge_location", "TEXT", "Where the patient was discharged to."),
        Column("insurance", "TEXT", "Insurance type, e.g. Medicare, Medicaid, Other."),
        Column("language", "TEXT", "Patient's stated language."),
        Column("marital_status", "TEXT", "Marital status."),
        Column("race", "TEXT", "Patient race/ethnicity as recorded."),
        Column("edregtime", "TEXT", "Emergency department registration time."),
        Column("edouttime", "TEXT", "Emergency department exit time."),
        Column("hospital_expire_flag", "INTEGER", "1 if patient died during this admission, else 0."),
    ],
)

DIAGNOSES_ICD = TableSchema(
    name="diagnoses_icd",
    module="hosp",
    description=(
        "Billed ICD diagnosis codes assigned to each hospital admission. One row per "
        "diagnosis code per admission (a single admission can have many rows). Use this "
        "table for questions about what conditions/diagnoses patients had, diagnosis "
        "frequency, or comorbidities."
    ),
    join_hints=(
        "Join keys: subject_id (links to patients), hadm_id (links to admissions). "
        "icd_code meaning is looked up in d_icd_diagnoses."
    ),
    columns=[
        Column("subject_id", "INTEGER", "Patient identifier."),
        Column("hadm_id", "INTEGER", "Admission identifier."),
        Column("icd_code", "TEXT", "ICD diagnosis code (format depends on icd_version)."),
        Column("seq_num", "INTEGER", "Priority/order in which the diagnosis was recorded."),
        Column("icd_version", "INTEGER", "9 or 10 — which ICD coding system the code uses."),
    ],
)

PROCEDURES_ICD = TableSchema(
    name="procedures_icd",
    module="hosp",
    description=(
        "Billed ICD procedure codes performed during each hospital admission. One row per "
        "procedure per admission. Use this table for questions about what procedures were "
        "performed, surgical history, or procedure frequency."
    ),
    join_hints=(
        "Join keys: subject_id (links to patients), hadm_id (links to admissions). "
        "icd_code meaning is looked up in d_icd_procedures."
    ),
    columns=[
        Column("subject_id", "INTEGER", "Patient identifier."),
        Column("hadm_id", "INTEGER", "Admission identifier."),
        Column("icd_code", "TEXT", "ICD procedure code."),
        Column("seq_num", "INTEGER", "Order in which the procedure was recorded."),
        Column("icd_version", "INTEGER", "9 or 10 — which ICD coding system the code uses."),
        Column("chartdate", "TEXT", "Date the procedure was charted."),
    ],
)
LABEVENTS = TableSchema(
    name="labevents",
    module="hosp",
    description=(
        "Laboratory test results for patients, e.g. blood chemistry, hematology, blood gas. "
        "One row per individual lab measurement. This table is very wide in *meaning* even "
        "though it has few columns — itemid determines which specific lab test (e.g. potassium, "
        "creatinine, white blood cell count) a row refers to; the actual test name/units are in "
        "d_labitems. Use this table for any question about specific lab values or lab result trends."
    ),
    wide=True,
    join_hints=(
        "Join keys: subject_id (patients), hadm_id (admissions), itemid (d_labitems for test name/units)."
    ),
    columns=[
        Column("labevent_id", "INTEGER", "Unique identifier for this lab event row."),
        Column("subject_id", "INTEGER", "Patient identifier."),
        Column("hadm_id", "INTEGER", "Admission identifier, may be NULL for outpatient labs."),
        Column("itemid", "INTEGER", "Identifies the specific lab test; look up name via d_labitems."),
        Column("charttime", "TEXT", "Time the lab specimen was charted/measured."),
        Column("value", "TEXT", "Raw result value as text."),
        Column("valuenum", "REAL", "Result value as a number, for numeric comparisons/thresholds."),
        Column("valueuom", "TEXT", "Unit of measurement for the result."),
        Column("flag", "TEXT", "'abnormal' if the result is outside the normal reference range."),
    ],
)

D_LABITEMS = TableSchema(
    name="d_labitems",
    module="hosp",
    description=(
        "Dictionary/lookup table mapping itemid to human-readable lab test names "
        "(e.g. 'Potassium', 'Creatinine', 'White Blood Cells') and the fluid/category. "
        "Use this table to translate itemid values found in labevents into readable test names."
    ),
    wide=True,
    join_hints="Join key: itemid (links to labevents.itemid).",
    columns=[
        Column("itemid", "INTEGER", "Unique identifier for a lab test type."),
        Column("label", "TEXT", "Human-readable test name, e.g. 'Potassium', 'Hemoglobin'."),
        Column("fluid", "TEXT", "Specimen fluid type, e.g. Blood, Urine."),
        Column("category", "TEXT", "Test category, e.g. Chemistry, Hematology, Blood Gas."),
    ],
)

CHARTEVENTS = TableSchema(
    name="chartevents",
    module="icu",
    description=(
        "Bedside vital-sign and clinical charting data from the ICU, e.g. heart rate, blood "
        "pressure, respiratory rate, temperature, oxygen saturation, Glasgow Coma Scale. "
        "Extremely high row count (this is the largest table in MIMIC-IV). itemid determines "
        "the specific measurement; the name/units are in d_items. Use this table for ICU vital "
        "signs and bedside-monitored measurements over time."
    ),
    wide=True,
    join_hints=(
        "Join keys: subject_id (patients), hadm_id (admissions), stay_id (icustays), "
        "itemid (d_items for measurement name/units)."
    ),
    columns=[
        Column("subject_id", "INTEGER", "Patient identifier."),
        Column("hadm_id", "INTEGER", "Admission identifier."),
        Column("stay_id", "INTEGER", "ICU stay identifier, links to icustays."),
        Column("itemid", "INTEGER", "Identifies the specific measurement; look up via d_items."),
        Column("charttime", "TEXT", "Time the measurement was charted."),
        Column("value", "TEXT", "Raw measurement value as text."),
        Column("valuenum", "REAL", "Measurement value as a number."),
        Column("valueuom", "TEXT", "Unit of measurement."),
    ],
)

D_ITEMS = TableSchema(
    name="d_items",
    module="icu",
    description=(
        "Dictionary/lookup table mapping itemid to human-readable names for ICU chart "
        "measurements (e.g. 'Heart Rate', 'Respiratory Rate', 'Arterial Blood Pressure'). "
        "Use this table to translate itemid values found in chartevents (and other ICU "
        "event tables) into readable measurement names."
    ),
    wide=True,
    join_hints="Join key: itemid (links to chartevents.itemid and other ICU event tables).",
    columns=[
        Column("itemid", "INTEGER", "Unique identifier for a chart measurement type."),
        Column("label", "TEXT", "Human-readable measurement name, e.g. 'Heart Rate'."),
        Column("category", "TEXT", "Measurement category, e.g. Routine Vital Signs, Labs."),
        Column("unitname", "TEXT", "Typical unit for this measurement."),
        Column("param_type", "TEXT", "Type of parameter, e.g. Numeric, Text, Date."),
    ],
)

PRESCRIPTIONS = TableSchema(
    name="prescriptions",
    module="hosp",
    description=(
        "Medication orders for patients during a hospital admission, including drug name, "
        "dose, route, and start/stop times. One row per prescribed medication order. Use this "
        "table for questions about what medications were prescribed, dosing, or drug frequency."
    ),
    wide=True,
    join_hints="Join keys: subject_id (patients), hadm_id (admissions).",
    columns=[
        Column("subject_id", "INTEGER", "Patient identifier."),
        Column("hadm_id", "INTEGER", "Admission identifier."),
        Column("starttime", "TEXT", "When the medication order started."),
        Column("stoptime", "TEXT", "When the medication order stopped."),
        Column("drug", "TEXT", "Name of the medication."),
        Column("dose_val_rx", "TEXT", "Prescribed dose value."),
        Column("dose_unit_rx", "TEXT", "Unit for the prescribed dose."),
        Column("route", "TEXT", "Route of administration, e.g. IV, PO, IM."),
    ],
)
ALL_TABLES: list[TableSchema] = [
    PATIENTS,
    ADMISSIONS,
    DIAGNOSES_ICD,
    PROCEDURES_ICD,
    LABEVENTS,
    D_LABITEMS,
    CHARTEVENTS,
    D_ITEMS,
    PRESCRIPTIONS,
]

TABLES_BY_NAME: dict[str, TableSchema] = {t.name: t for t in ALL_TABLES}
print(PATIENTS)