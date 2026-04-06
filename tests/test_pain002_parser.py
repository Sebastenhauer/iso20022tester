"""Tests für den pain.002.001.10 Response Parser.

Testet:
- XML-Parsing verschiedener pain.002 Strukturen
- Korrelation mit pain.001 Testfall-Ergebnissen
- Fehlerbehandlung bei ungültigen Dateien
- Pipeline-Integration (process_responses)
"""

import os
import tempfile
from decimal import Decimal

import pytest

from src.models.testcase import (
    DebtorInfo,
    ExpectedResult,
    Pain002Result,
    PaymentInstruction,
    PaymentType,
    TestCaseResult,
    Transaction,
    TransactionStatusInfo,
    ValidationResult,
)
from src.response_parser.pain002_parser import (
    correlate_with_results,
    parse_pain002,
    parse_pain002_files,
)


# --- Hilfsfunktionen: pain.002 XML erzeugen ---

PAIN002_NS = "urn:iso:std:iso:20022:tech:xsd:pain.002.001.10"


def _pain002_xml(
    pain002_msg_id: str = "STATUS-001",
    original_msg_id: str = "MSG-abc123def456",
    group_status: str = None,
    pmt_inf_id: str = "PMT-abc123def456",
    pmt_inf_status: str = None,
    transactions: list = None,
) -> str:
    """Erzeugt eine pain.002.001.10 XML-Datei als String."""
    grp_sts = f"<GrpSts>{group_status}</GrpSts>" if group_status else ""

    pmt_inf_sts_tag = f"<PmtInfSts>{pmt_inf_status}</PmtInfSts>" if pmt_inf_status else ""

    tx_xml = ""
    if transactions:
        for tx in transactions:
            reason = ""
            if tx.get("reason_code"):
                reason = f"""<StsRsnInf>
                    <Rsn><Cd>{tx['reason_code']}</Cd></Rsn>
                    {f"<AddtlInf>{tx.get('reason_additional', '')}</AddtlInf>" if tx.get('reason_additional') else ""}
                </StsRsnInf>"""
            tx_xml += f"""<TxInfAndSts>
                <OrgnlEndToEndId>{tx['e2e_id']}</OrgnlEndToEndId>
                <TxSts>{tx['status']}</TxSts>
                {reason}
            </TxInfAndSts>
            """

    pmt_inf_block = f"""<OrgnlPmtInfAndSts>
        <OrgnlPmtInfId>{pmt_inf_id}</OrgnlPmtInfId>
        {pmt_inf_sts_tag}
        {tx_xml}
    </OrgnlPmtInfAndSts>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{PAIN002_NS}">
    <CstmrPmtStsRpt>
        <GrpHdr>
            <MsgId>{pain002_msg_id}</MsgId>
            <CreDtTm>2025-01-15T10:30:00</CreDtTm>
        </GrpHdr>
        <OrgnlGrpInfAndSts>
            <OrgnlMsgId>{original_msg_id}</OrgnlMsgId>
            <OrgnlMsgNmId>pain.001.001.09</OrgnlMsgNmId>
            {grp_sts}
        </OrgnlGrpInfAndSts>
        {pmt_inf_block}
    </CstmrPmtStsRpt>
</Document>"""


def _write_pain002(tmpdir: str, xml_content: str, filename: str = "response.xml") -> str:
    """Schreibt pain.002 XML in eine temporäre Datei."""
    path = os.path.join(tmpdir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_content)
    return path


def _make_result(
    testcase_id: str = "TC-001",
    payment_type: PaymentType = PaymentType.SEPA,
) -> TestCaseResult:
    """Erzeugt ein Minimal-TestCaseResult."""
    return TestCaseResult(
        testcase_id=testcase_id,
        titel="Test",
        payment_type=payment_type,
        expected_result=ExpectedResult.OK,
        xsd_valid=True,
        overall_pass=True,
    )


def _make_instruction(
    msg_id: str = "MSG-abc123def456",
    pmt_inf_id: str = "PMT-abc123def456",
    e2e_ids: list = None,
) -> PaymentInstruction:
    """Erzeugt eine Minimal-PaymentInstruction."""
    if e2e_ids is None:
        e2e_ids = ["E2E-aaa111bbb222"]
    transactions = [
        Transaction(
            end_to_end_id=e2e,
            amount=Decimal("100.00"),
            currency="EUR",
            creditor_name="Test Creditor",
            creditor_iban="DE89370400440532013000",
        )
        for e2e in e2e_ids
    ]
    return PaymentInstruction(
        msg_id=msg_id,
        pmt_inf_id=pmt_inf_id,
        cre_dt_tm="2025-01-15T09:00:00",
        reqd_exctn_dt="2025-01-16",
        debtor=DebtorInfo(name="Debtor AG", iban="CH9300762011623852957"),
        transactions=transactions,
    )


# =========================================================================
# Parsing: Grundlegende Struktur
# =========================================================================

class TestParse002Basic:
    def test_parse_accepted(self, tmp_path):
        """ACTC Gruppen-Status wird korrekt geparst."""
        xml = _pain002_xml(group_status="ACTC")
        path = _write_pain002(str(tmp_path), xml)
        result = parse_pain002(path)

        assert result.pain002_msg_id == "STATUS-001"
        assert result.original_msg_id == "MSG-abc123def456"
        assert result.group_status == "ACTC"
        assert result.pain002_file_path == path

    def test_parse_rejected(self, tmp_path):
        """RJCT Gruppen-Status wird korrekt geparst."""
        xml = _pain002_xml(group_status="RJCT")
        path = _write_pain002(str(tmp_path), xml)
        result = parse_pain002(path)

        assert result.group_status == "RJCT"

    def test_parse_pending(self, tmp_path):
        """PDNG Gruppen-Status wird korrekt geparst."""
        xml = _pain002_xml(group_status="PDNG")
        path = _write_pain002(str(tmp_path), xml)
        result = parse_pain002(path)

        assert result.group_status == "PDNG"

    def test_parse_no_group_status(self, tmp_path):
        """Fehlender Gruppen-Status → None."""
        xml = _pain002_xml()
        path = _write_pain002(str(tmp_path), xml)
        result = parse_pain002(path)

        assert result.group_status is None

    def test_parse_payment_info_status(self, tmp_path):
        """PmtInfSts wird korrekt geparst."""
        xml = _pain002_xml(pmt_inf_status="ACSP")
        path = _write_pain002(str(tmp_path), xml)
        result = parse_pain002(path)

        assert result.payment_status == "ACSP"
        assert result.original_pmt_inf_id == "PMT-abc123def456"


# =========================================================================
# Parsing: Transaktionsstatus
# =========================================================================

class TestParse002Transactions:
    def test_parse_single_transaction(self, tmp_path):
        """Einzelne Transaktion mit Status und Grund."""
        xml = _pain002_xml(
            transactions=[{
                "e2e_id": "E2E-aaa111bbb222",
                "status": "RJCT",
                "reason_code": "AC01",
                "reason_additional": "Konto ungueltig",
            }]
        )
        path = _write_pain002(str(tmp_path), xml)
        result = parse_pain002(path)

        assert len(result.transaction_statuses) == 1
        tx = result.transaction_statuses[0]
        assert tx.end_to_end_id == "E2E-aaa111bbb222"
        assert tx.status == "RJCT"
        assert tx.reason_code == "AC01"
        assert tx.reason_additional == "Konto ungueltig"

    def test_parse_multiple_transactions(self, tmp_path):
        """Mehrere Transaktionen in einer pain.002."""
        xml = _pain002_xml(
            transactions=[
                {"e2e_id": "E2E-tx1", "status": "ACTC"},
                {"e2e_id": "E2E-tx2", "status": "RJCT", "reason_code": "AM04"},
            ]
        )
        path = _write_pain002(str(tmp_path), xml)
        result = parse_pain002(path)

        assert len(result.transaction_statuses) == 2
        assert result.transaction_statuses[0].status == "ACTC"
        assert result.transaction_statuses[1].status == "RJCT"
        assert result.transaction_statuses[1].reason_code == "AM04"

    def test_parse_transaction_no_reason(self, tmp_path):
        """Transaktion ohne Reason → None."""
        xml = _pain002_xml(
            transactions=[{"e2e_id": "E2E-ok", "status": "ACSC"}]
        )
        path = _write_pain002(str(tmp_path), xml)
        result = parse_pain002(path)

        tx = result.transaction_statuses[0]
        assert tx.status == "ACSC"
        assert tx.reason_code is None
        assert tx.reason_additional is None


# =========================================================================
# Parsing: Fehlerbehandlung
# =========================================================================

class TestParse002Errors:
    def test_parse_invalid_xml(self, tmp_path):
        """Ungültiges XML wirft Exception."""
        path = os.path.join(str(tmp_path), "bad.xml")
        with open(path, "w") as f:
            f.write("<<<not xml>>>")
        with pytest.raises(Exception):
            parse_pain002(path)

    def test_parse_nonexistent_file(self):
        """Nicht existierende Datei wirft Exception."""
        with pytest.raises(Exception):
            parse_pain002("/nonexistent/pain002.xml")

    def test_parse_multiple_files_with_errors(self, tmp_path):
        """parse_pain002_files sammelt Fehler statt abzubrechen."""
        good = _write_pain002(str(tmp_path), _pain002_xml(group_status="ACTC"), "good.xml")
        bad_path = os.path.join(str(tmp_path), "bad.xml")
        with open(bad_path, "w") as f:
            f.write("<<<not xml>>>")

        results, errors = parse_pain002_files([good, bad_path])

        assert len(results) == 1
        assert results[0].group_status == "ACTC"
        assert len(errors) == 1
        assert "bad.xml" in errors[0]


# =========================================================================
# Korrelation: MsgId-Matching
# =========================================================================

class TestCorrelation:
    def test_correlate_by_msg_id(self):
        """Korrelation über OrgnlMsgId → instruction.msg_id."""
        result = _make_result("TC-001")
        instr = _make_instruction(msg_id="MSG-abc123def456")

        p002 = Pain002Result(
            pain002_msg_id="STATUS-001",
            original_msg_id="MSG-abc123def456",
            group_status="ACTC",
            transaction_statuses=[],
        )

        updated = correlate_with_results(
            [p002], [result], {"TC-001": instr}
        )

        assert len(updated) == 1
        assert updated[0].pain002_result is not None
        assert updated[0].pain002_result.group_status == "ACTC"

    def test_correlate_by_e2e_id(self):
        """Fallback-Korrelation über EndToEndId."""
        result = _make_result("TC-001")
        instr = _make_instruction(
            msg_id="MSG-other",
            e2e_ids=["E2E-match123"],
        )

        p002 = Pain002Result(
            pain002_msg_id="STATUS-002",
            original_msg_id="MSG-unknown",
            group_status="RJCT",
            transaction_statuses=[
                TransactionStatusInfo(
                    end_to_end_id="E2E-match123",
                    status="RJCT",
                    reason_code="AC01",
                )
            ],
        )

        updated = correlate_with_results(
            [p002], [result], {"TC-001": instr}
        )

        assert updated[0].pain002_result is not None
        assert updated[0].pain002_result.group_status == "RJCT"

    def test_no_correlation_found(self):
        """Keine Korrelation → pain002_result bleibt None."""
        result = _make_result("TC-001")
        instr = _make_instruction(msg_id="MSG-abc123def456")

        p002 = Pain002Result(
            pain002_msg_id="STATUS-003",
            original_msg_id="MSG-nomatch",
            group_status="ACTC",
            transaction_statuses=[],
        )

        updated = correlate_with_results(
            [p002], [result], {"TC-001": instr}
        )

        assert updated[0].pain002_result is None

    def test_correlate_multiple_results(self):
        """Mehrere Testfälle mit mehreren pain.002-Antworten."""
        result1 = _make_result("TC-001")
        result2 = _make_result("TC-002")
        instr1 = _make_instruction(msg_id="MSG-001", e2e_ids=["E2E-001"])
        instr2 = _make_instruction(msg_id="MSG-002", e2e_ids=["E2E-002"])

        p002_1 = Pain002Result(
            pain002_msg_id="STS-1",
            original_msg_id="MSG-001",
            group_status="ACTC",
            transaction_statuses=[],
        )
        p002_2 = Pain002Result(
            pain002_msg_id="STS-2",
            original_msg_id="MSG-002",
            group_status="RJCT",
            transaction_statuses=[
                TransactionStatusInfo(
                    end_to_end_id="E2E-002",
                    status="RJCT",
                    reason_code="AM04",
                )
            ],
        )

        updated = correlate_with_results(
            [p002_1, p002_2],
            [result1, result2],
            {"TC-001": instr1, "TC-002": instr2},
        )

        tc1 = next(r for r in updated if r.testcase_id == "TC-001")
        tc2 = next(r for r in updated if r.testcase_id == "TC-002")

        assert tc1.pain002_result.group_status == "ACTC"
        assert tc2.pain002_result.group_status == "RJCT"
        assert tc2.pain002_result.transaction_statuses[0].reason_code == "AM04"


# =========================================================================
# Integration: Pipeline.process_responses
# =========================================================================

class TestPipelineIntegration:
    def test_process_responses_full_cycle(self, tmp_path):
        """Vollständiger Zyklus: pain.001 generieren → pain.002 parsen → korrelieren."""
        from openpyxl import Workbook
        from src.models.config import AppConfig
        from src.pipeline import PaymentTestPipeline
        from src.input_handler.excel_parser import parse_excel

        # 1. Excel mit einem SEPA-Testfall erstellen
        headers = [
            "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis", "Zahlungstyp",
            "Betrag", "Waehrung", "Debtor Name", "Debtor IBAN", "Debtor BIC",
            "Creditor Name", "Creditor IBAN", "Creditor BIC", "Verwendungszweck",
            "ViolateRule", "Weitere Testdaten", "Erwartete API-Antwort", "Bemerkungen",
        ]
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        ws.append([
            "TC-P002", "pain.002 Test", "Response Parsing", "OK", "SEPA",
            500.00, "EUR", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None, None, None, None, None,
        ])
        excel_path = os.path.join(str(tmp_path), "test.xlsx")
        wb.save(excel_path)

        # 2. Pipeline: pain.001 generieren
        config = AppConfig(
            output_path=str(tmp_path),
            xsd_path="schemas/pain.001.001.09.ch.03.xsd",
            seed=42,
            report_format="txt",
        )
        pipeline = PaymentTestPipeline(config, seed=42)

        testcases, _ = parse_excel(excel_path)
        output_dir = os.path.join(str(tmp_path), "output")
        os.makedirs(output_dir, exist_ok=True)
        results = pipeline.process(testcases, output_dir)

        assert len(results) == 1
        assert results[0].overall_pass is True

        # 3. Generierte MsgId aus instructions holen
        instr = pipeline.instructions["TC-P002"]
        msg_id = instr.msg_id
        e2e_id = instr.transactions[0].end_to_end_id

        # 4. Simulierte pain.002-Antwort erstellen
        pain002_xml = _pain002_xml(
            original_msg_id=msg_id,
            group_status="ACTC",
            transactions=[{
                "e2e_id": e2e_id,
                "status": "ACSC",
            }],
        )
        pain002_path = _write_pain002(str(tmp_path), pain002_xml)

        # 5. pain.002 parsen und korrelieren
        updated, errors = pipeline.process_responses(
            [pain002_path], results, verbose=True
        )

        assert len(errors) == 0
        assert len(updated) == 1
        assert updated[0].pain002_result is not None
        assert updated[0].pain002_result.group_status == "ACTC"
        assert updated[0].pain002_result.original_msg_id == msg_id
        assert len(updated[0].pain002_result.transaction_statuses) == 1
        assert updated[0].pain002_result.transaction_statuses[0].status == "ACSC"


# =========================================================================
# Modell-Tests
# =========================================================================

class TestModels:
    def test_transaction_status_info(self):
        """TransactionStatusInfo Pydantic-Modell."""
        ts = TransactionStatusInfo(
            end_to_end_id="E2E-test",
            status="RJCT",
            reason_code="AC01",
            reason_additional="Invalid account",
        )
        assert ts.end_to_end_id == "E2E-test"
        assert ts.status == "RJCT"
        assert ts.reason_code == "AC01"

    def test_pain002_result_defaults(self):
        """Pain002Result mit Defaults."""
        p = Pain002Result(
            pain002_msg_id="S1",
            original_msg_id="M1",
        )
        assert p.group_status is None
        assert p.payment_status is None
        assert p.transaction_statuses == []
        assert p.pain002_file_path is None

    def test_testcase_result_with_pain002(self):
        """TestCaseResult mit pain002_result-Feld."""
        p002 = Pain002Result(
            pain002_msg_id="S1",
            original_msg_id="M1",
            group_status="ACTC",
        )
        r = _make_result("TC-001")
        r_with = r.model_copy(update={"pain002_result": p002})
        assert r_with.pain002_result is not None
        assert r_with.pain002_result.group_status == "ACTC"

    def test_testcase_result_without_pain002(self):
        """TestCaseResult ohne pain002_result (Rückwärtskompatibilität)."""
        r = _make_result("TC-001")
        assert r.pain002_result is None
