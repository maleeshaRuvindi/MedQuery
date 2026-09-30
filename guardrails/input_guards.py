import re
import logging
from presidio_analyzer import AnalyzerEngine
from .exceptions import GuardrailError

logger = logging.getLogger(__name__)

SQL_INJECTION_PATTERNS = [
    r"drop\s+table",
    r"delete\s+from",
    r"insert\s+into",
    r"update\s+\w+\s+set",
    r"alter\s+table",
    r"truncate\s+table",
    r"--",
    r";.*?;",
]

PROMPT_INJECTION_PHRASES = [
    "ignore previous instructions",
    "ignore above instructions",
    "disregard your instructions",
    "forget everything",
    "reveal your instructions",
    "new persona",
    "act as",
]

_analyzer = None

def _get_analyzer() -> AnalyzerEngine:
    global _analyzer
    if _analyzer is None:
        _analyzer = AnalyzerEngine()
    return _analyzer


def check_sql_injection(text: str) -> None:
    lower = text.lower()
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, lower):
            raise GuardrailError(
                message="Your query contains disallowed SQL keywords. Please rephrase.",
                layer="input",
                rule="sql_injection"
            )


def check_prompt_injection(text: str) -> None:
    lower = text.lower()
    for phrase in PROMPT_INJECTION_PHRASES:
        if phrase in lower:
            raise GuardrailError(
                message="Your query contains instruction-override language. Please ask a clinical question.",
                layer="input",
                rule="prompt_injection"
            )


def check_pii_in_input(text: str) -> None:
    analyzer = _get_analyzer()
    entities = analyzer.analyze(text, language="en")
    if entities:
        types = list({e.entity_type for e in entities})
        raise GuardrailError(
            message=f"Your query contains personal identifiers ({types}). "
                    f"Please ask questions without including patient-identifying information.",
            layer="input",
            rule="pii_in_query"
        )


def run_input_guards(user_query: str) -> None:
    """
    Runs all input guardrails in order.
    Raises GuardrailError on first violation.
    """
    check_sql_injection(user_query)
    check_prompt_injection(user_query)
    check_pii_in_input(user_query)
    logger.info("Input guardrails passed.")