from guardrails.input_guards import check_pii_in_input
import pytest
from guardrails.exceptions import GuardrailError

def test_pii_in_input():
    with pytest.raises(GuardrailError) as exc_info:
        check_pii_in_input("My email is john.smith@example.com")

    err = exc_info.value
    assert err.layer == "input"
    assert err.rule == "pii_in_query"
    assert "personal identifiers" in err.message

def test_no_pii_in_input():
    response=check_pii_in_input("unique number of patients")
    assert response==None


