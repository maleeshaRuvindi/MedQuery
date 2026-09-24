import logging
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from .exceptions import GuardrailError

logger = logging.getLogger(__name__)

_analyzer = None
_anonymizer = None


def _get_engines():
    global _analyzer, _anonymizer
    if _analyzer is None:
        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()
    return _analyzer, _anonymizer


def scrub_results(results: list[dict]) -> list[dict]:
    """
    Scrubs PII from SQL results before they are sent to the LLM.
    Called inside execute_sql in tools.py.
    """
    analyzer, anonymizer = _get_engines()
    scrubbed = []
    for row in results:
        clean_row = {}
        for key, value in row.items():
            text = str(value)
            entities = analyzer.analyze(text, language="en")
            if entities:
                result = anonymizer.anonymize(text, entities)
                clean_row[key] = result.text
                logger.warning(f"PII scrubbed from column '{key}': "
                               f"{[e.entity_type for e in entities]}")
            else:
                clean_row[key] = value
        scrubbed.append(clean_row)
    return scrubbed


def check_row_count(results: list[dict], threshold: int = 10000) -> None:
    if len(results) > threshold:
        raise GuardrailError(
            message=f"Query returned {len(results)} rows — exceeds safe threshold of {threshold}.",
            layer="output",
            rule="row_count_threshold"
        )


def scrub_final_response(text: str) -> str:
    """
    Final PII check on the LLM's natural language answer
    before it is returned to the user.
    """
    analyzer, anonymizer = _get_engines()
    entities = analyzer.analyze(text, language="en")
    if entities:
        logger.warning(f"PII detected in final LLM response: "
                       f"{[e.entity_type for e in entities]}")
        return anonymizer.anonymize(text, entities).text
    return text


def run_output_guards(results: list[dict], llm_response: str) -> str:
    """
    Runs all output guardrails.
    Returns safe final response string.
    """
    check_row_count(results)
    safe_response = scrub_final_response(llm_response)
    logger.info("Output guardrails passed.")
    return safe_response