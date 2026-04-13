"""Tests fuer src/payment_types/pacs008/defaults.py."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.models.pacs008 import Pacs008Flavor, Pacs008TestCase, SettlementMethod
from src.models.testcase import ExpectedResult
from src.payment_types.pacs008 import defaults as D


class TestResolveSettlementDate:
    def test_eur_next_business_day(self):
        """EUR -> TARGET2 Kalender, T+1."""
        mon = date(2026, 4, 6)  # Monday
        result = D.resolve_settlement_date("EUR", base=mon)
        assert result.weekday() < 5
        # Naechster Banktag, typischerweise Dienstag
        assert result > mon

    def test_friday_jumps_over_weekend(self):
        fri = date(2026, 4, 10)  # Friday
        result = D.resolve_settlement_date("EUR", base=fri)
        # Weekend is Sa/Su, next business day should be Mo or later
        assert result.weekday() == 0  # Monday, unless TARGET2 holiday

    def test_chf_uses_swiss_calendar(self):
        mon = date(2026, 4, 6)
        result = D.resolve_settlement_date("CHF", base=mon)
        assert result.weekday() < 5
        assert result > mon

    def test_custom_offset(self):
        mon = date(2026, 4, 6)
        t0 = D.resolve_settlement_date("CHF", base=mon, offset_days=0)
        t5 = D.resolve_settlement_date("CHF", base=mon, offset_days=5)
        assert t5 > t0

    def test_iso_string_wrapper(self):
        s = D.resolve_settlement_date_str("EUR", base=date(2026, 4, 6))
        assert len(s) == 10
        assert s[4] == "-"


class TestApplyDefaultsToTestCase:
    def _minimal_tc(self, **overrides):
        defaults = dict(
            testcase_id="TC-DEF",
            titel="T",
            ziel="Z",
            expected_result=ExpectedResult.OK,
            amount=Decimal("1000"),
            currency="EUR",
        )
        defaults.update(overrides)
        return Pacs008TestCase(**defaults)

    def test_fills_charge_bearer(self):
        tc = self._minimal_tc()
        assert tc.charge_bearer is None
        D.apply_defaults_to_testcase(tc)
        assert tc.charge_bearer == "SHAR"

    def test_preserves_explicit_charge_bearer(self):
        tc = self._minimal_tc(charge_bearer="DEBT")
        D.apply_defaults_to_testcase(tc)
        assert tc.charge_bearer == "DEBT"

    def test_fills_settlement_date(self):
        tc = self._minimal_tc()
        assert tc.interbank_settlement_date is None
        D.apply_defaults_to_testcase(tc)
        assert tc.interbank_settlement_date is not None
        assert len(tc.interbank_settlement_date) == 10

    def test_preserves_explicit_settlement_date(self):
        tc = self._minimal_tc(interbank_settlement_date="2026-12-31")
        D.apply_defaults_to_testcase(tc)
        assert tc.interbank_settlement_date == "2026-12-31"

    def test_fills_default_intermediary_for_cbpr(self):
        tc = self._minimal_tc()
        D.apply_defaults_to_testcase(tc)
        assert tc.intermediary_agent_1_bic == D.DEFAULT_INTERMEDIARY_1_BIC

    def test_preserves_explicit_intermediary(self):
        tc = self._minimal_tc(intermediary_agent_1_bic="COBADEFFXXX")
        D.apply_defaults_to_testcase(tc)
        assert tc.intermediary_agent_1_bic == "COBADEFFXXX"

    def test_preserves_explicit_intermediary_clr_sys(self):
        tc = self._minimal_tc(intermediary_agent_1_clr_sys_mmb_id="021000021")
        D.apply_defaults_to_testcase(tc)
        # User hat CLRSYS angegeben -> Intermediary-Slot ist belegt,
        # BIC-Default soll NICHT gesetzt werden
        assert tc.intermediary_agent_1_bic is None

    def test_no_intermediary_for_non_cbpr_flavor(self):
        tc = self._minimal_tc(flavor=Pacs008Flavor.TARGET2)
        D.apply_defaults_to_testcase(tc)
        assert tc.intermediary_agent_1_bic is None

    def test_does_not_touch_instg_instd_agents(self):
        tc = self._minimal_tc()
        D.apply_defaults_to_testcase(tc)
        # InstgAgt/InstdAgt haben bewusst KEINEN Default
        assert tc.instructing_agent_bic is None
        assert tc.instructed_agent_bic is None

    def test_does_not_touch_debtor_creditor_agents(self):
        tc = self._minimal_tc()
        D.apply_defaults_to_testcase(tc)
        assert tc.debtor_agent_bic is None
        assert tc.creditor_agent_bic is None


class TestConstants:
    def test_bah_idr_default(self):
        assert D.BAH_MSG_DEF_IDR == "pacs.008.001.08"
        assert D.BAH_BIZ_SVC == "swift.cbprplus.04"

    def test_settlement_method_default(self):
        assert D.DEFAULT_SETTLEMENT_METHOD == "INDA"

    def test_charge_bearer_default(self):
        assert D.DEFAULT_CHARGE_BEARER == "SHAR"
