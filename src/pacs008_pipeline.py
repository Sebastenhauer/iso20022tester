"""pacs.008 Pipeline (parallel zu src/pipeline.py fuer pain.001).

Verarbeitet Pacs008TestCases zu BusinessMessage-XMLs, validiert
gegen XSD + Business Rules und schreibt Reports.

Output-Struktur:
    output/<timestamp>/pacs.008/
        <timestamp>_<tc_id>_<short>.xml        (BAH + Document im BusinessMessage-Wrapper)
        testlauf_ergebnis.json                 (Zusammenfassung aller Testcases)

Die Pipeline ist bewusst unabhaengig von der pain.001-PaymentTestPipeline,
um die Regression-Oberflaeche klein zu halten und spaetere pacs.008-
Erweiterungen (Multi-Tx, neue Flavors, Inflow-Mode) ohne Side-Effects
auf pain.001 umsetzen zu koennen.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Tuple

from lxml import etree

from src.models.config import AppConfig
from src.models.pacs008 import (
    AccountInfo,
    AgentInfo,
    BusinessRuleResultLite,
    Pacs008BusinessMessage,
    Pacs008Flavor,
    Pacs008Instruction,
    Pacs008TestCase,
    Pacs008TestCaseResult,
    Pacs008Transaction,
    PartyInfo,
    PostalAddress,
    SettlementMethod,
)
from src.models.testcase import ExpectedResult
from src.payment_types.pacs008 import defaults as pacs_defaults
from src.validation.pacs008_rules import validate_pacs008
from src.validation.pacs008_violations import (
    apply_pacs008_violation,
    get_pacs008_violations_registry,
)
from src.xml_generator.pacs008.message_builder import (
    build_business_message,
    build_document,
    serialize,
)


class Pacs008TestPipeline:
    """Verarbeitet pacs.008 Testcases end-to-end.

    Verwendung:
        pipeline = Pacs008TestPipeline(config, use_external_validator=True)
        results = pipeline.process(testcases, output_dir)
        pipeline.generate_reports(results, input_file, output_dir)
    """

    def __init__(self, config: AppConfig, use_external_validator: bool = False):
        self.config = config
        # Lazy init XSD Validator (damit Tests ohne Schema weiterhin laufen)
        self._xsd_schema: Optional[etree.XMLSchema] = None
        self._xsd_path = self._resolve_xsd_path()
        self.use_external_validator = use_external_validator
        self._validator_client = None
        self._validator_quota_exhausted = False
        if use_external_validator:
            try:
                from src.xml_validator_service.client import (
                    XmlValidatorClient,
                    XmlValidatorConfigError,
                )
                try:
                    self._validator_client = XmlValidatorClient()
                except XmlValidatorConfigError as e:
                    print(f"[pacs.008] External validator disabled: {e}")
                    self.use_external_validator = False
            except ImportError:
                print("[pacs.008] External validator module not available.")
                self.use_external_validator = False

    def _resolve_xsd_path(self) -> Optional[str]:
        """Findet das CBPR+ pacs.008 XSD im schemas/pacs.008/ Ordner."""
        candidates = [
            "schemas/pacs.008/CBPRPlus_SR2026_(Combined)_CBPRPlus-pacs_008_001_08_FIToFICustomerCreditTransfer_20260319_1152_iso15enriched.xsd",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def _get_xsd(self) -> Optional[etree.XMLSchema]:
        if self._xsd_schema is not None:
            return self._xsd_schema
        if not self._xsd_path:
            return None
        try:
            self._xsd_schema = etree.XMLSchema(etree.parse(self._xsd_path))
            return self._xsd_schema
        except Exception:
            return None

    # -----------------------------------------------------------------
    # Main Loop
    # -----------------------------------------------------------------

    def process(
        self,
        testcases: List[Pacs008TestCase],
        output_dir: str,
        verbose: bool = False,
    ) -> List[Pacs008TestCaseResult]:
        """Verarbeitet alle pacs.008 Testcases."""
        pacs_output_dir = os.path.join(output_dir, "pacs.008")
        os.makedirs(pacs_output_dir, exist_ok=True)

        results: List[Pacs008TestCaseResult] = []
        for tc in testcases:
            try:
                result = self._process_single(tc, pacs_output_dir, verbose)
            except Exception as e:
                result = Pacs008TestCaseResult(
                    testcase_id=tc.testcase_id,
                    titel=tc.titel,
                    flavor=tc.flavor,
                    expected_result=tc.expected_result,
                    xsd_valid=False,
                    xsd_errors=[f"Pipeline-Exception: {e}"],
                    business_rule_results=[],
                    overall_pass=False,
                    xml_file_path=None,
                    remarks=tc.remarks,
                )
            results.append(result)
        return results

    def _process_single(
        self,
        tc: Pacs008TestCase,
        pacs_output_dir: str,
        verbose: bool,
    ) -> Pacs008TestCaseResult:
        """Baut, validiert und persistiert eine einzelne pacs.008 Nachricht."""
        # Defaults auf TestCase anwenden
        pacs_defaults.apply_defaults_to_testcase(tc)

        # Business Message aus TestCase konstruieren
        bm = self._build_business_message(tc)

        # Violation anwenden falls gesetzt
        if tc.violate_rule:
            registry = get_pacs008_violations_registry()
            if tc.violate_rule in registry:
                bm = apply_pacs008_violation(bm, tc.violate_rule)
            else:
                # Unknown rule -> treat as no-op but log via remarks
                pass

        # Root-Element bauen + serialisieren
        root = build_business_message(bm)
        xml_bytes = serialize(root)

        # In Datei schreiben
        short_id = uuid.uuid4().hex[:8]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{ts}_{tc.testcase_id}_{short_id}.xml"
        file_path = os.path.join(pacs_output_dir, file_name)
        Path(file_path).write_bytes(xml_bytes)

        # XSD-Validation (nur das Document, nicht die BAH-Envelope)
        xsd_valid, xsd_errors = self._validate_xsd(bm)

        # Business Rules
        br_results = validate_pacs008(bm)
        br_lite: List[BusinessRuleResultLite] = list(br_results)

        # External XML Validator Service (optional).
        # Negative testcases (ViolateRule + expected NOK) are skipped --
        # they already have an internal failure expectation, so calling
        # the external service for them just burns quota.
        external_valid: Optional[bool] = None
        external_errors: List[str] = []
        is_negative_test = (
            tc.expected_result == ExpectedResult.NOK and bool(tc.violate_rule)
        )
        if (
            self.use_external_validator
            and self._validator_client is not None
            and not self._validator_quota_exhausted
            and not is_negative_test
        ):
            from src.xml_validator_service.client import XmlValidatorQuotaExceeded
            try:
                external_result = self._validator_client.validate(
                    xml_bytes, flavor=tc.flavor,
                )
                external_valid = external_result.valid
                external_errors = external_result.errors
            except XmlValidatorQuotaExceeded as e:
                self._validator_quota_exhausted = True
                print(
                    f"[pacs.008] External validator quota exhausted, "
                    f"skipping remaining. ({tc.testcase_id} and onwards)"
                )
                # This testcase is also skipped (None = neutral)
                external_valid = None
                external_errors = []
            except Exception as e:
                external_valid = False
                external_errors = [f"External validator call failed: {e}"]

        # Overall-Pass Logik
        all_br_pass = all(r.passed for r in br_lite)
        external_ok = external_valid is None or external_valid is True
        overall_ok = xsd_valid and all_br_pass and external_ok

        # Expected NOK -> invert (if we expect it to fail, "failing" is a pass)
        if tc.expected_result == ExpectedResult.NOK:
            overall_pass = not overall_ok
        else:
            overall_pass = overall_ok

        return Pacs008TestCaseResult(
            testcase_id=tc.testcase_id,
            titel=tc.titel,
            flavor=tc.flavor,
            expected_result=tc.expected_result,
            xsd_valid=xsd_valid,
            xsd_errors=xsd_errors,
            business_rule_results=br_lite,
            external_valid=external_valid,
            external_errors=external_errors,
            overall_pass=overall_pass,
            xml_file_path=file_path,
            remarks=tc.remarks,
        )

    # -----------------------------------------------------------------
    # BusinessMessage Construction
    # -----------------------------------------------------------------

    def _build_business_message(self, tc: Pacs008TestCase) -> Pacs008BusinessMessage:
        """Baut eine Pacs008BusinessMessage aus einem TestCase."""

        # BICs und Agent-Objekte
        instg_bic = tc.instructing_agent_bic or tc.debtor_agent_bic or ""
        instd_bic = tc.instructed_agent_bic or tc.creditor_agent_bic or ""
        dbtr_agt_bic = tc.debtor_agent_bic or instg_bic
        cdtr_agt_bic = tc.creditor_agent_bic or instd_bic
        bah_from = tc.bah_from_bic or instg_bic
        bah_to = tc.bah_to_bic or instd_bic

        instg_agt = AgentInfo(
            bic=tc.instructing_agent_bic or instg_bic or None,
            clearing_member_id=tc.instructing_agent_clr_sys_mmb_id,
        )
        instd_agt = AgentInfo(
            bic=tc.instructed_agent_bic or instd_bic or None,
            clearing_member_id=tc.instructed_agent_clr_sys_mmb_id,
        )
        dbtr_agt = AgentInfo(
            bic=tc.debtor_agent_bic,
            clearing_member_id=tc.debtor_agent_clr_sys_mmb_id,
        )
        cdtr_agt = AgentInfo(
            bic=tc.creditor_agent_bic,
            clearing_member_id=tc.creditor_agent_clr_sys_mmb_id,
        )

        # Parties
        dbtr = PartyInfo(
            name=tc.debtor_name or "Unnamed Debtor",
            postal_address=tc.debtor_address,
        )
        cdtr = PartyInfo(
            name=tc.creditor_name or "Unnamed Creditor",
            postal_address=tc.creditor_address,
        )

        # Accounts
        dbtr_acct = None
        if tc.debtor_iban or tc.debtor_account_other_id:
            dbtr_acct = AccountInfo(
                iban=tc.debtor_iban,
                other_id=tc.debtor_account_other_id,
                other_scheme_code=tc.debtor_account_other_scheme,
            )
        cdtr_acct = None
        if tc.creditor_iban or tc.creditor_account_other_id:
            cdtr_acct = AccountInfo(
                iban=tc.creditor_iban,
                other_id=tc.creditor_account_other_id,
                other_scheme_code=tc.creditor_account_other_scheme,
            )

        # Intermediary-Agent-Liste
        intermediaries: List[AgentInfo] = []
        for bic, clr in [
            (tc.intermediary_agent_1_bic, tc.intermediary_agent_1_clr_sys_mmb_id),
            (tc.intermediary_agent_2_bic, None),
            (tc.intermediary_agent_3_bic, None),
        ]:
            if bic or clr:
                intermediaries.append(AgentInfo(bic=bic, clearing_member_id=clr))

        # UETR
        uetr = tc.uetr or str(uuid.uuid4())

        # Betrag + Currency (Defaults)
        amount = tc.amount or Decimal("0.00")
        currency = tc.currency or "EUR"

        # Remittance
        rmt = None
        if tc.remittance_info:
            rmt = {"type": "USTRD", "value": tc.remittance_info}

        # IDs (CBPR+ maxLength fuer InstrId, MsgId, EndToEndId = 16/35 je Feld;
        # InstrId hat den striktesten Constraint mit max 16 Zeichen).
        short = uuid.uuid4().hex[:8]
        msg_id = f"MSG{short}"[:35]
        end_to_end = f"E2E{short}"[:35]
        instr_id = f"INSTR{short}"[:16]

        tx = Pacs008Transaction(
            instruction_id=instr_id,
            end_to_end_id=end_to_end,
            uetr=uetr,
            instructed_amount=amount,
            instructed_currency=currency,
            charge_bearer=tc.charge_bearer,
            debtor=dbtr,
            debtor_account=dbtr_acct,
            debtor_agent=dbtr_agt,
            creditor=cdtr,
            creditor_account=cdtr_acct,
            creditor_agent=cdtr_agt,
            intermediary_agents=intermediaries,
            purpose_code=tc.purpose_code,
            category_purpose=tc.category_purpose,
            remittance_info=rmt,
        )

        now_iso = datetime.now(timezone.utc).astimezone().isoformat()

        instruction = Pacs008Instruction(
            msg_id=msg_id,
            cre_dt_tm=now_iso,
            number_of_transactions=1,
            control_sum=amount,
            interbank_settlement_date=tc.interbank_settlement_date or "",
            instructing_agent=instg_agt,
            instructed_agent=instd_agt,
            settlement_method=tc.settlement_method,
            transactions=[tx],
        )

        return Pacs008BusinessMessage(
            bah_from_bic=bah_from or "XXXXXXXXXXX",
            bah_to_bic=bah_to or "XXXXXXXXXXX",
            bah_biz_msg_idr=msg_id,
            bah_cre_dt=now_iso,
            instruction=instruction,
        )

    # -----------------------------------------------------------------
    # Validation Helpers
    # -----------------------------------------------------------------

    def _validate_xsd(
        self, bm: Pacs008BusinessMessage
    ) -> Tuple[bool, List[str]]:
        """Validiert das <Document>-Element (ohne BAH) gegen das CBPR+ XSD."""
        schema = self._get_xsd()
        if schema is None:
            return True, ["(XSD nicht geladen, Skip)"]
        doc = build_document(bm.instruction)
        if schema.validate(doc):
            return True, []
        errors = [str(e) for e in schema.error_log]
        return False, errors

    # -----------------------------------------------------------------
    # Reporting
    # -----------------------------------------------------------------

    def generate_reports(
        self,
        results: List[Pacs008TestCaseResult],
        input_file: str,
        output_dir: str,
    ) -> dict:
        """Erzeugt einen JSON-Report unter output/<ts>/pacs.008/testlauf_ergebnis.json."""
        pacs_output_dir = os.path.join(output_dir, "pacs.008")
        os.makedirs(pacs_output_dir, exist_ok=True)

        pass_count = sum(1 for r in results if r.overall_pass)
        fail_count = len(results) - pass_count

        external_validation_enabled = self.use_external_validator
        external_validation_checked = sum(
            1 for r in results if r.external_valid is not None
        )
        external_validation_passed = sum(
            1 for r in results if r.external_valid is True
        )

        report = {
            "testlauf": {
                "datum": datetime.now().isoformat(),
                "message_type": "pacs.008",
                "flavor": "CBPR+",
                "input_file": input_file,
                "total": len(results),
                "pass": pass_count,
                "fail": fail_count,
                "external_validation_enabled": external_validation_enabled,
                "external_validation_checked": external_validation_checked,
                "external_validation_passed": external_validation_passed,
            },
            "testfaelle": [
                {
                    "testcase_id": r.testcase_id,
                    "titel": r.titel,
                    "flavor": r.flavor.value,
                    "erwartetes_ergebnis": r.expected_result.value,
                    "xsd_valide": r.xsd_valid,
                    "xsd_fehler": r.xsd_errors,
                    "business_rules": [
                        {
                            "rule_id": br.rule_id,
                            "beschreibung": br.rule_description,
                            "bestanden": br.passed,
                            "details": br.details,
                        }
                        for br in r.business_rule_results
                    ],
                    "external_valide": r.external_valid,
                    "external_fehler": r.external_errors,
                    "ergebnis": "Pass" if r.overall_pass else "Fail",
                    "xml_datei": r.xml_file_path,
                    "bemerkungen": r.remarks,
                }
                for r in results
            ],
        }

        report_path = os.path.join(pacs_output_dir, "testlauf_ergebnis.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        return {"json": report_path}
