"""Modell-Roundtrip-Tests fuer pacs.008."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.models.pacs008 import (
    AccountInfo,
    AgentInfo,
    ChargesInfo,
    Pacs008BusinessMessage,
    Pacs008Flavor,
    Pacs008Instruction,
    Pacs008TestCase,
    Pacs008Transaction,
    PartyInfo,
    PostalAddress,
    SettlementMethod,
)
from src.models.testcase import ExpectedResult


# ---------------------------------------------------------------------------
# Leaf objects
# ---------------------------------------------------------------------------

class TestPostalAddress:
    def test_empty_detected(self):
        assert PostalAddress().is_empty() is True

    def test_populated(self):
        addr = PostalAddress(
            street_name="Bahnhofstrasse",
            building_number="42",
            postal_code="8001",
            town_name="Zurich",
            country="CH",
        )
        assert not addr.is_empty()
        assert addr.country == "CH"


class TestAgentInfo:
    def test_bic_only(self):
        a = AgentInfo(bic="UBSWCHZH80A")
        assert a.is_bic_only
        assert a.has_identification

    def test_clearing_only(self):
        a = AgentInfo(clearing_system_code="USABA", clearing_member_id="021000021")
        assert not a.is_bic_only
        assert a.has_identification

    def test_both(self):
        a = AgentInfo(bic="CHASUS33XXX", clearing_member_id="021000021")
        assert not a.is_bic_only
        assert a.has_identification

    def test_empty_has_no_id(self):
        a = AgentInfo(name="Nameless")
        assert not a.has_identification


class TestAccountInfo:
    def test_iban(self):
        a = AccountInfo(iban="CH9300762011623852957")
        assert a.has_id

    def test_other(self):
        a = AccountInfo(other_id="1234567", other_scheme_code="BBAN")
        assert a.has_id

    def test_empty(self):
        assert not AccountInfo().has_id


class TestChargesInfo:
    def test_valid(self):
        c = ChargesInfo(
            amount=Decimal("15.00"),
            currency="EUR",
            agent=AgentInfo(bic="DEUTDEFFXXX"),
        )
        assert c.amount == Decimal("15.00")

    def test_missing_agent_fails(self):
        with pytest.raises(ValidationError):
            ChargesInfo(amount=Decimal("15.00"), currency="EUR")  # type: ignore


# ---------------------------------------------------------------------------
# Transaction & Instruction
# ---------------------------------------------------------------------------

def _minimal_agent(bic: str) -> AgentInfo:
    return AgentInfo(bic=bic)


def _minimal_party(name: str, country: str = "CH") -> PartyInfo:
    return PartyInfo(
        name=name,
        postal_address=PostalAddress(
            street_name="Teststrasse",
            building_number="1",
            postal_code="8001",
            town_name="Zurich",
            country=country,
        ),
    )


def _minimal_tx() -> Pacs008Transaction:
    return Pacs008Transaction(
        end_to_end_id="E2E-TEST-001",
        uetr="8a562c67-ca16-48ba-b074-65581be6f001",
        instructed_amount=Decimal("1000.00"),
        instructed_currency="EUR",
        charge_bearer="SHAR",
        debtor=_minimal_party("Muster AG", "CH"),
        debtor_account=AccountInfo(iban="CH9300762011623852957"),
        debtor_agent=_minimal_agent("UBSWCHZH80A"),
        creditor=_minimal_party("Empfaenger GmbH", "DE"),
        creditor_account=AccountInfo(iban="DE89370400440532013000"),
        creditor_agent=_minimal_agent("DEUTDEFFXXX"),
    )


class TestPacs008Transaction:
    def test_minimal(self):
        tx = _minimal_tx()
        assert tx.uetr
        assert tx.instructed_currency == "EUR"
        assert tx.debtor.name == "Muster AG"
        assert tx.creditor_agent.bic == "DEUTDEFFXXX"

    def test_with_intermediaries(self):
        tx = _minimal_tx()
        tx.intermediary_agents = [
            _minimal_agent("CHASUS33XXX"),
            _minimal_agent("COBADEFFXXX"),
        ]
        assert len(tx.intermediary_agents) == 2

    def test_with_charges(self):
        tx = _minimal_tx()
        tx.charges_info = [
            ChargesInfo(
                amount=Decimal("10.00"), currency="EUR",
                agent=_minimal_agent("UBSWCHZH80A"),
            ),
            ChargesInfo(
                amount=Decimal("5.00"), currency="EUR",
                agent=_minimal_agent("DEUTDEFFXXX"),
            ),
        ]
        assert len(tx.charges_info) == 2
        assert tx.charges_info[0].amount == Decimal("10.00")

    def test_missing_uetr_fails(self):
        with pytest.raises(ValidationError):
            Pacs008Transaction(
                end_to_end_id="E2E-TEST-001",
                # uetr missing
                instructed_amount=Decimal("1000.00"),
                instructed_currency="EUR",
                debtor=_minimal_party("A"),
                debtor_agent=_minimal_agent("UBSWCHZH80A"),
                creditor=_minimal_party("B", "DE"),
                creditor_agent=_minimal_agent("DEUTDEFFXXX"),
            )  # type: ignore


class TestPacs008Instruction:
    def test_minimal(self):
        tx = _minimal_tx()
        instr = Pacs008Instruction(
            msg_id="MSG-TEST-001",
            cre_dt_tm="2026-04-06T14:00:00",
            number_of_transactions=1,
            control_sum=Decimal("1000.00"),
            interbank_settlement_date="2026-04-08",
            instructing_agent=_minimal_agent("UBSWCHZH80A"),
            instructed_agent=_minimal_agent("DEUTDEFFXXX"),
            transactions=[tx],
        )
        assert instr.settlement_method == SettlementMethod.INDA
        assert len(instr.transactions) == 1

    def test_multi_tx_control_sum(self):
        tx1 = _minimal_tx()
        tx2 = _minimal_tx()
        tx2.end_to_end_id = "E2E-TEST-002"
        tx2.instructed_amount = Decimal("500.00")
        instr = Pacs008Instruction(
            msg_id="MSG-TEST-002",
            cre_dt_tm="2026-04-06T14:00:00",
            number_of_transactions=2,
            control_sum=Decimal("1500.00"),
            interbank_settlement_date="2026-04-08",
            instructing_agent=_minimal_agent("UBSWCHZH80A"),
            instructed_agent=_minimal_agent("DEUTDEFFXXX"),
            transactions=[tx1, tx2],
        )
        assert instr.number_of_transactions == 2
        assert instr.control_sum == Decimal("1500.00")


# ---------------------------------------------------------------------------
# TestCase & BusinessMessage
# ---------------------------------------------------------------------------

class TestPacs008TestCase:
    def test_minimal(self):
        tc = Pacs008TestCase(
            testcase_id="TC-PACS-001",
            titel="Smoke",
            ziel="Minimal test",
            expected_result=ExpectedResult.OK,
            debtor_name="Muster AG",
            debtor_iban="CH9300762011623852957",
            debtor_agent_bic="UBSWCHZH80A",
            creditor_name="Empfaenger GmbH",
            creditor_iban="DE89370400440532013000",
            creditor_agent_bic="DEUTDEFFXXX",
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        assert tc.flavor == Pacs008Flavor.CBPR_PLUS
        assert tc.settlement_method == SettlementMethod.INDA
        assert tc.overrides == {}

    def test_with_overrides(self):
        tc = Pacs008TestCase(
            testcase_id="TC-PACS-002",
            titel="Override Test",
            ziel="Dot-Notation",
            expected_result=ExpectedResult.OK,
            overrides={
                "IntrmyAgt1.FinInstnId.BICFI": "CHASUS33XXX",
                "ChrgsInf[0].Amt": "12.50",
            },
        )
        assert tc.overrides["IntrmyAgt1.FinInstnId.BICFI"] == "CHASUS33XXX"

    def test_flavor_enum(self):
        assert Pacs008Flavor.CBPR_PLUS.value == "CBPR+"
        assert Pacs008Flavor.TARGET2.value == "TARGET2"


class TestPacs008BusinessMessage:
    def test_wrap(self):
        tx = _minimal_tx()
        instr = Pacs008Instruction(
            msg_id="MSG-BIZ-001",
            cre_dt_tm="2026-04-06T14:00:00",
            number_of_transactions=1,
            control_sum=Decimal("1000.00"),
            interbank_settlement_date="2026-04-08",
            instructing_agent=_minimal_agent("UBSWCHZH80A"),
            instructed_agent=_minimal_agent("DEUTDEFFXXX"),
            transactions=[tx],
        )
        bm = Pacs008BusinessMessage(
            bah_from_bic="UBSWCHZH80A",
            bah_to_bic="DEUTDEFFXXX",
            bah_biz_msg_idr="MSG-BIZ-001",
            bah_cre_dt="2026-04-06T14:00:00",
            instruction=instr,
        )
        assert bm.bah_msg_def_idr == "pacs.008.001.08"
        assert bm.bah_biz_svc == "swift.cbprplus.04"
        assert bm.instruction.msg_id == "MSG-BIZ-001"
