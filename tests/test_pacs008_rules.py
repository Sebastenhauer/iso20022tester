"""Tests fuer BR-CBPR-PACS-001..015 (pacs.008 Business Rules)."""

from decimal import Decimal

import pytest

from src.models.pacs008 import (
    AccountInfo,
    AgentInfo,
    ChargesInfo,
    Pacs008BusinessMessage,
    Pacs008Instruction,
    Pacs008Transaction,
    PartyInfo,
    PostalAddress,
    SettlementMethod,
)
from src.validation.pacs008_rules import validate_pacs008


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _valid_message(**instr_overrides) -> Pacs008BusinessMessage:
    ubs = AgentInfo(bic="UBSWCHZH80A")
    deut = AgentInfo(bic="DEUTDEFFXXX")
    dbtr = PartyInfo(
        name="Muster AG",
        postal_address=PostalAddress(
            street_name="Bahnhofstrasse", building_number="42",
            postal_code="8001", town_name="Zurich", country="CH",
        ),
    )
    cdtr = PartyInfo(
        name="Empfaenger GmbH",
        postal_address=PostalAddress(
            street_name="Unter den Linden", building_number="7",
            postal_code="10117", town_name="Berlin", country="DE",
        ),
    )
    tx = Pacs008Transaction(
        end_to_end_id="E2E-TEST-001",
        uetr="8a562c67-ca16-48ba-b074-65581be6001",  # invalid intentionally? no, valid v4
        instructed_amount=Decimal("1000.00"),
        instructed_currency="EUR",
        charge_bearer="SHAR",
        debtor=dbtr,
        debtor_account=AccountInfo(iban="CH5604835012345678009"),
        debtor_agent=ubs,
        creditor=cdtr,
        creditor_account=AccountInfo(iban="DE89370400440532013000"),
        creditor_agent=deut,
    )
    # Produce a real v4 uuid
    tx.uetr = "8a562c67-ca16-48ba-b074-65581be6f001"
    instr_kwargs = dict(
        msg_id="MSG-TEST-001",
        cre_dt_tm="2026-04-06T14:30:00+00:00",
        number_of_transactions=1,
        control_sum=Decimal("1000.00"),
        interbank_settlement_date="2026-04-08",  # Wednesday
        instructing_agent=ubs,
        instructed_agent=deut,
        transactions=[tx],
    )
    instr_kwargs.update(instr_overrides)
    instr = Pacs008Instruction(**instr_kwargs)
    return Pacs008BusinessMessage(
        bah_from_bic="UBSWCHZH80A",
        bah_to_bic="DEUTDEFFXXX",
        bah_biz_msg_idr="MSG-TEST-001",
        bah_cre_dt="2026-04-06T14:30:00+00:00",
        instruction=instr,
    )


def _rules_by_id(results):
    by_id = {}
    for r in results:
        by_id.setdefault(r.rule_id, []).append(r)
    return by_id


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_all_rules_pass_for_valid_message():
    bm = _valid_message()
    results = validate_pacs008(bm)
    by_id = _rules_by_id(results)

    expected_rule_ids = {
        "BR-CBPR-PACS-001", "BR-CBPR-PACS-002", "BR-CBPR-PACS-003",
        "BR-CBPR-PACS-004", "BR-CBPR-PACS-005", "BR-CBPR-PACS-006",
        "BR-CBPR-PACS-007", "BR-CBPR-PACS-008", "BR-CBPR-PACS-009",
        "BR-CBPR-PACS-010", "BR-CBPR-PACS-011", "BR-CBPR-PACS-013",
        "BR-CBPR-PACS-014", "BR-CBPR-PACS-015",
    }
    # BR-CBPR-PACS-012 only fires when charges_info present, nicht in valid_message
    actual_ids = set(by_id.keys())
    assert expected_rule_ids.issubset(actual_ids), f"Missing: {expected_rule_ids - actual_ids}"

    for rule_id, rs in by_id.items():
        for r in rs:
            assert r.passed, f"{rule_id} failed: {r.details}"


# ---------------------------------------------------------------------------
# Individual negative tests
# ---------------------------------------------------------------------------

class TestBahRules:
    def test_wrong_msg_def_idr(self):
        bm = _valid_message()
        bm.bah_msg_def_idr = "pacs.008.001.09"
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-007"]
        assert len(r) == 1 and not r[0].passed

    def test_wrong_biz_svc(self):
        bm = _valid_message()
        bm.bah_biz_svc = "swift.wrong.01"
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-008"]
        assert len(r) == 1 and not r[0].passed


class TestGroupHeaderRules:
    def test_nb_of_txs_mismatch(self):
        bm = _valid_message()
        bm.instruction.number_of_transactions = 3
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-013"]
        assert len(r) == 1 and not r[0].passed

    def test_ctrl_sum_mismatch(self):
        bm = _valid_message()
        bm.instruction.control_sum = Decimal("999.99")
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-014"]
        assert len(r) == 1 and not r[0].passed

    def test_settlement_date_is_weekend(self):
        bm = _valid_message(interbank_settlement_date="2026-04-11")  # Saturday
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-009"]
        assert len(r) == 1 and not r[0].passed

    def test_settlement_date_bad_format(self):
        bm = _valid_message(interbank_settlement_date="08.04.2026")
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-009"]
        assert len(r) == 1 and not r[0].passed


class TestTransactionRules:
    def test_missing_uetr(self):
        bm = _valid_message()
        bm.instruction.transactions[0].uetr = ""
        results = validate_pacs008(bm)
        r001 = [r for r in results if r.rule_id == "BR-CBPR-PACS-001"]
        assert len(r001) == 1 and not r001[0].passed

    def test_invalid_uetr_format(self):
        bm = _valid_message()
        bm.instruction.transactions[0].uetr = "not-a-uuid"
        results = validate_pacs008(bm)
        r015 = [r for r in results if r.rule_id == "BR-CBPR-PACS-015"]
        assert len(r015) == 1 and not r015[0].passed

    def test_instg_agt_without_id(self):
        bm = _valid_message()
        bm.instruction.instructing_agent = AgentInfo(name="Nameless")
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-002"]
        assert len(r) >= 1 and not any(x.passed for x in r)

    def test_instd_agt_without_id(self):
        bm = _valid_message()
        bm.instruction.instructed_agent = AgentInfo(name="Nameless")
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-003"]
        assert len(r) >= 1 and not any(x.passed for x in r)

    def test_sttlm_mtd_cove_rejected(self):
        bm = _valid_message(settlement_method=SettlementMethod.COVE)
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-004"]
        assert len(r) >= 1 and not any(x.passed for x in r)

    def test_sttlm_mtd_inga_accepted(self):
        bm = _valid_message(settlement_method=SettlementMethod.INGA)
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-004"]
        assert all(x.passed for x in r)

    def test_creditor_missing_address(self):
        bm = _valid_message()
        bm.instruction.transactions[0].creditor = PartyInfo(name="Nameless")
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-005"]
        assert len(r) == 1 and not r[0].passed

    def test_debtor_missing_address(self):
        bm = _valid_message()
        bm.instruction.transactions[0].debtor = PartyInfo(name="Nameless")
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-006"]
        assert len(r) == 1 and not r[0].passed

    def test_invalid_charge_bearer(self):
        bm = _valid_message()
        bm.instruction.transactions[0].charge_bearer = "XXXX"
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-010"]
        assert len(r) == 1 and not r[0].passed

    def test_invalid_currency(self):
        bm = _valid_message()
        bm.instruction.transactions[0].instructed_currency = "XX9"
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-011"]
        assert len(r) == 1 and not r[0].passed


class TestChargesInfo:
    def test_charges_without_agent_id_fails(self):
        bm = _valid_message()
        bm.instruction.transactions[0].charges_info = [
            ChargesInfo(
                amount=Decimal("10.00"), currency="EUR",
                agent=AgentInfo(name="Nameless"),  # no BIC, no ClrSys
            ),
        ]
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-012"]
        assert len(r) == 1 and not r[0].passed

    def test_charges_with_valid_agent(self):
        bm = _valid_message()
        bm.instruction.transactions[0].charges_info = [
            ChargesInfo(
                amount=Decimal("10.00"), currency="EUR",
                agent=AgentInfo(bic="UBSWCHZH80A"),
            ),
        ]
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-012"]
        assert all(x.passed for x in r)

    def test_no_charges_no_rule(self):
        bm = _valid_message()
        bm.instruction.transactions[0].charges_info = []
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-012"]
        assert len(r) == 0


class TestCredChargesRequired:
    """BR-CBPR-PACS-016: CRED verlangt ChrgsInf."""

    def test_cred_without_charges_fails(self):
        bm = _valid_message()
        bm.instruction.transactions[0].charge_bearer = "CRED"
        bm.instruction.transactions[0].charges_info = []
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-016"]
        assert len(r) == 1 and not r[0].passed

    def test_cred_with_zero_charges_passes(self):
        bm = _valid_message()
        bm.instruction.transactions[0].charge_bearer = "CRED"
        bm.instruction.transactions[0].charges_info = [
            ChargesInfo(
                amount=Decimal("0.00"), currency="EUR",
                agent=AgentInfo(bic="UBSWCHZH80A"),
            ),
        ]
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-016"]
        assert len(r) == 1 and r[0].passed

    def test_debt_without_charges_no_rule(self):
        """DEBT: ChrgsInf optional — rule 016 does not fire."""
        bm = _valid_message()
        bm.instruction.transactions[0].charge_bearer = "DEBT"
        bm.instruction.transactions[0].charges_info = []
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-016"]
        assert len(r) == 0

    def test_shar_without_charges_no_rule(self):
        """SHAR: ChrgsInf optional — rule 016 does not fire."""
        bm = _valid_message()
        # Default is SHAR, charges empty
        bm.instruction.transactions[0].charges_info = []
        results = validate_pacs008(bm)
        r = [r for r in results if r.rule_id == "BR-CBPR-PACS-016"]
        assert len(r) == 0


class TestRuleCatalogPresence:
    def test_all_ids_in_catalog(self):
        from src.validation.rule_catalog import get_rule
        for i in range(1, 17):  # 001..016
            rid = f"BR-CBPR-PACS-{i:03d}"
            r = get_rule(rid)
            assert r is not None, f"{rid} not in catalog"
            assert r.category == "CBPR-PACS"
