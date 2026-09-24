import re
import logging
import sqlglot
import sqlglot.expressions as exp
from .exceptions import GuardrailError

logger = logging.getLogger(__name__)

ALLOWED_TABLES = {
    'admissions', 'diagnoses_icd', 'drgcodes', 'd_hcpcs',
    'd_icd_diagnoses', 'd_icd_procedures', 'd_labitems', 'emar',
    'emar_detail', 'hcpcsevents', 'labevents', 'microbiologyevents',
    'omr', 'patients', 'pharmacy', 'poe', 'poe_detail',
    'prescriptions', 'procedures_icd', 'provider', 'services', 'transfers'
}

BLOCKED_COLUMNS = {
    "name", "first_name", "last_name", "ssn",
    "dob", "date_of_birth", "phone", "address", "email"
}

MAX_ROWS = 1000


def check_select_only(parsed: exp.Expression) -> None:
    if not isinstance(parsed, exp.Select):
        raise GuardrailError(
            message="Only SELECT queries are permitted.",
            layer="sql",
            rule="select_only"
        )


def check_allowed_tables(parsed: exp.Expression) -> None:
    tables_used = {t.name.lower() for t in parsed.find_all(exp.Table)}
    disallowed = tables_used - ALLOWED_TABLES
    if disallowed:
        raise GuardrailError(
            message=f"Query references unauthorized tables: {disallowed}",
            layer="sql",
            rule="table_whitelist"
        )


def check_blocked_columns(parsed: exp.Expression) -> None:
    cols_used = {c.name.lower() for c in parsed.find_all(exp.Column)}
    blocked = cols_used & BLOCKED_COLUMNS
    if blocked:
        raise GuardrailError(
            message=f"Query selects sensitive columns: {blocked}",
            layer="sql",
            rule="blocked_columns"
        )


def enforce_row_limit(sql: str, parsed: exp.Expression) -> str:
    limit_node = parsed.args.get("limit")
    if limit_node is None:
        return sql.rstrip(";") + f" LIMIT {MAX_ROWS}"

    try:
        limit_val = int(limit_node.this.name)
        if limit_val > MAX_ROWS:
            parsed.set("limit", exp.Limit(this=exp.Literal.number(MAX_ROWS)))
            return parsed.sql()  # no dialect = generic SQL, fine for SQLite
    except (AttributeError, ValueError):
        parsed.set("limit", exp.Limit(this=exp.Literal.number(MAX_ROWS)))
        return parsed.sql()

    return sql


def run_sql_guards(sql: str) -> str:
    """
    Validates and sanitizes generated SQL.
    Returns safe SQL string.
    Raises GuardrailError on violation.
    """
    try:
        parsed = sqlglot.parse_one(sql)
    except Exception as e:
        raise GuardrailError(
            message=f"SQL parsing failed: {e}",
            layer="sql",
            rule="parse_failure"
        )

    check_select_only(parsed)
    check_allowed_tables(parsed)
    check_blocked_columns(parsed)
    safe_sql = enforce_row_limit(sql, parsed)

    logger.info(f"SQL guardrails passed. Safe SQL: {safe_sql}")
    return safe_sql