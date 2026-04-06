"""Tests fuer currency-aware Amount-Formatierung (WP-12 Regression-Guard).

Aus der FINaplo-Validation (WP-12 Runde 1) kam der Fehlercode D00007
'Invalid currency code or too many decimal digits' fuer TC-PCS-004
(JPY). Root Cause: _fmt_amount quantisierte immer auf 0.01.

Der Fix macht den Formatter currency-aware. Dieser Testsatz schuetzt
vor Regression.
"""

from decimal import Decimal

import pytest
from lxml import etree

from src.models.pacs008 import (
    AccountInfo,
    AgentInfo,
    ChargesInfo,
    Pacs008Instruction,
    Pacs008Transaction,
    PartyInfo,
    PostalAddress,
)
from src.xml_generator.pacs008.builders import (
    _decimals_for_currency,
    _fmt_amount,
)
from src.xml_generator.pacs008.message_builder import build_document
from src.xml_generator.pacs008.namespaces import PACS008_NS

NS = {"p": PACS008_NS}


class TestFmtAmount:
    def test_eur_two_decimals(self):
        assert _fmt_amount(Decimal("1000"), "EUR") == "1000.00"

    def test_usd_two_decimals(self):
        assert _fmt_amount(Decimal("1500.5"), "USD") == "1500.50"

    def test_jpy_zero_decimals(self):
        assert _fmt_amount(Decimal("500000"), "JPY") == "500000"

    def test_jpy_strips_fractional(self):
        assert _fmt_amount(Decimal("500000.00"), "JPY") == "500000"

    def test_krw_zero_decimals(self):
        assert _fmt_amount(Decimal("1234567"), "KRW") == "1234567"

    def test_isk_zero_decimals(self):
        assert _fmt_amount(Decimal("100"), "ISK") == "100"

    def test_bhd_three_decimals(self):
        assert _fmt_amount(Decimal("100"), "BHD") == "100.000"

    def test_kwd_three_decimals(self):
        assert _fmt_amount(Decimal("50.5"), "KWD") == "50.500"

    def test_unknown_currency_default_two(self):
        assert _fmt_amount(Decimal("100"), "XXX") == "100.00"

    def test_no_currency_default_two(self):
        assert _fmt_amount(Decimal("100"), None) == "100.00"


class TestDecimalsForCurrency:
    @pytest.mark.parametrize("ccy,expected", [
        ("EUR", 2), ("USD", 2), ("GBP", 2), ("CHF", 2),
        ("JPY", 0), ("KRW", 0), ("ISK", 0), ("VND", 0), ("BIF", 0),
        ("BHD", 3), ("KWD", 3), ("OMR", 3), ("JOD", 3),
        ("XXX", 2),  # unknown
        (None, 2),
        ("jpy", 0),  # case-insensitive
        ("eur", 2),
    ])
    def test_decimal_lookup(self, ccy, expected):
        assert _decimals_for_currency(ccy) == expected


class TestJpyInGeneratedXml:
    def test_jpy_amount_has_no_decimals(self):
        """Integration: das komplette XML enthaelt JPY-Betrag ohne Dezimalen."""
        ubs = AgentInfo(bic="UBSWCHZH80A")
        mizuho = AgentInfo(bic="MHCBJPJTXXX")
        dbtr = PartyInfo(
            name="Muster AG",
            postal_address=PostalAddress(
                street_name="Bahnhofstrasse", building_number="42",
                postal_code="8001", town_name="Zurich", country="CH",
            ),
        )
        cdtr = PartyInfo(
            name="Tokyo Corp",
            postal_address=PostalAddress(
                street_name="Marunouchi", building_number="1-1-1",
                postal_code="100-0005", town_name="Tokyo", country="JP",
            ),
        )
        tx = Pacs008Transaction(
            end_to_end_id="E2E-JPY-001",
            uetr="00000000-1111-4222-8333-444444444444",
            instructed_amount=Decimal("500000"),
            instructed_currency="JPY",
            charge_bearer="SHAR",
            debtor=dbtr,
            debtor_account=AccountInfo(iban="CH9300762011623852957"),
            debtor_agent=ubs,
            creditor=cdtr,
            creditor_agent=mizuho,
        )
        instr = Pacs008Instruction(
            msg_id="MSG-JPY-001",
            cre_dt_tm="2026-04-06T14:30:00+00:00",
            number_of_transactions=1,
            control_sum=Decimal("500000"),
            interbank_settlement_date="2026-04-08",
            instructing_agent=ubs,
            instructed_agent=mizuho,
            transactions=[tx],
        )
        doc = build_document(instr)

        instd_amt = doc.find(".//p:CdtTrfTxInf/p:InstdAmt", NS)
        intr_amt = doc.find(".//p:CdtTrfTxInf/p:IntrBkSttlmAmt", NS)
        assert instd_amt.text == "500000"
        assert instd_amt.get("Ccy") == "JPY"
        assert intr_amt.text == "500000"
        assert "." not in instd_amt.text
        assert "." not in intr_amt.text

    def test_charges_info_bhd_three_decimals(self):
        """Charges in BHD (Bahrain Dinar, 3 Dezimalstellen)."""
        from src.xml_generator.pacs008.builders import build_charges_info
        root = etree.Element(f"{{{PACS008_NS}}}X")
        ci = ChargesInfo(
            amount=Decimal("10.5"), currency="BHD",
            agent=AgentInfo(bic="NBOBBHBMXXX"),
        )
        build_charges_info(root, ci)
        amt = root.find(".//p:ChrgsInf/p:Amt", NS)
        assert amt.text == "10.500"
        assert amt.get("Ccy") == "BHD"
