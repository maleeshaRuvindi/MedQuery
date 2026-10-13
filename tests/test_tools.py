from agent.tools import is_safe_query,load_schemas,get_schema,execute_sql
import pytest
import sqlite3
import agent.tools as tools
import json
def test_is_safe_query():
    assert is_safe_query("select * from patients")==True
    assert is_safe_query("select * from patients;DROP TABLE patients;")==False
    assert is_safe_query("DROP TABLE patients")==False
    assert is_safe_query("invalid query")==False

def test_load_schemas():
    schemas = load_schemas()
    assert isinstance(schemas, dict)
    assert len(schemas) > 0

def test_get_schema_single():
    result= get_schema.invoke({"table_names":["patients"]})
    assert isinstance(result,str)
    assert "subject_id" in result
    assert "gender" in result

def test_get_schema_multiple():
    tables=["patients","admissions","diagnoses_icd"]
    result= get_schema.invoke({"table_names":tables})
    for table in tables:
        assert table in result

def test_get_schema_invalid():
    assert get_schema.invoke({"table_names":["invalid table"]})==""


@pytest.fixture
def sample_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE patients (subject_id INTEGER, gender TEXT, anchor_age INTEGER)"
    )
    conn.executemany(
        "INSERT INTO patients VALUES (?, ?, ?)",
        [(i, "F" if i % 2 else "M", 30 + i) for i in range(1, 31)],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(tools, "DB_PATH", str(db))
    return db

def test_execute_sql_returns_rows(sample_db):
    result = json.loads(
        tools.execute_sql.invoke({"query": "SELECT subject_id, gender FROM patients WHERE subject_id <= 3"})
    )
    assert result["row_count"] == 3
    assert result["columns"] == ["subject_id", "gender"]
    assert len(result["data"]) == 3

def test_execute_sql_caps_output_at_20_rows(sample_db):
    result = json.loads(
        tools.execute_sql.invoke({"query": "SELECT * FROM patients"})
    )
    assert result["row_count"] == 30
    assert len(result["data"]) == 20


def test_execute_sql_empty_result(sample_db):
    result = json.loads(
        tools.execute_sql.invoke({"query": "SELECT * FROM patients WHERE subject_id < 0"})
    )
    assert result["row_count"] == 0


def test_execute_sql_blocks_write_queries(sample_db):
    result = tools.execute_sql.invoke({"query": "DROP TABLE patients"})
    assert "blocked by safety guardrail" in result


def test_execute_sql_bad_sql_returns_error(sample_db):
    result = tools.execute_sql.invoke({"query": "SELECT * FROM no_such_table"})
    assert result.startswith("Query blocked by safety guardrail")





