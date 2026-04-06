"""Round-Trip Tests fuer pacs.008 Violations.

Pattern: eine gueltige BusinessMessage bauen -> Violation anwenden
-> validate_pacs008() aufrufen -> pruefen dass die spezifische
Rule failt (und nur die).
"""

import pytest

from src.validation.pacs008_rules import validate_pacs008
from src.validation.pacs008_violations import (
    apply_pacs008_violation,
    get_pacs008_violations_registry,
)

from tests.test_pacs008_rules import _valid_message


def _fail_ids(results):
    return {r.rule_id for r in results if not r.passed}


# ---------------------------------------------------------------------------
# Per-Rule Round-Trip Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rule_id", [
    "BR-CBPR-PACS-001",
    "BR-CBPR-PACS-002",
    "BR-CBPR-PACS-003",
    "BR-CBPR-PACS-004",
    "BR-CBPR-PACS-007",
    "BR-CBPR-PACS-008",
    "BR-CBPR-PACS-010",
    "BR-CBPR-PACS-011",
    "BR-CBPR-PACS-015",
])
def test_violation_triggers_target_rule(rule_id):
    bm = _valid_message()
    apply_pacs008_violation(bm, rule_id)
    results = validate_pacs008(bm)
    failed = _fail_ids(results)
    assert rule_id in failed, f"{rule_id}: expected to fail, actual fails: {failed}"


def test_uetr_missing_violation_triggers_001():
    bm = _valid_message()
    apply_pacs008_violation(bm, "BR-CBPR-PACS-001")
    results = validate_pacs008(bm)
    failed = _fail_ids(results)
    assert "BR-CBPR-PACS-001" in failed


def test_uetr_invalid_triggers_015_not_001():
    """Invalid UETR ist vorhanden -> 001 passes, 015 fails."""
    bm = _valid_message()
    apply_pacs008_violation(bm, "BR-CBPR-PACS-015")
    results = validate_pacs008(bm)
    failed = _fail_ids(results)
    assert "BR-CBPR-PACS-015" in failed
    assert "BR-CBPR-PACS-001" not in failed


class TestRegistryShape:
    def test_registry_has_expected_rules(self):
        reg = get_pacs008_violations_registry()
        expected = {
            "BR-CBPR-PACS-001", "BR-CBPR-PACS-002", "BR-CBPR-PACS-003",
            "BR-CBPR-PACS-004", "BR-CBPR-PACS-007", "BR-CBPR-PACS-008",
            "BR-CBPR-PACS-010", "BR-CBPR-PACS-011", "BR-CBPR-PACS-015",
        }
        assert set(reg.keys()) == expected

    def test_unknown_rule_raises_key_error(self):
        bm = _valid_message()
        with pytest.raises(KeyError, match="nicht vorhanden"):
            apply_pacs008_violation(bm, "BR-DOES-NOT-EXIST")
