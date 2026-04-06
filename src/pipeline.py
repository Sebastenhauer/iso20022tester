"""Pipeline: Orchestriert den gesamten Testlauf.

Trennt die Verarbeitungslogik vom CLI (main.py).
Kann unabhängig von der Kommandozeile verwendet und getestet werden.
"""

import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from lxml import etree

from src.data_factory.generator import DataFactory
from src.mapping.field_mapper import validate_and_map_overrides
from src.models.config import AppConfig
from src.models.testcase import (
    ExpectedResult,
    Pain001Document,
    Pain002Result,
    PaymentInstruction,
    PaymentType,
    Standard,
    TestCase,
    TestCaseResult,
)
from src.response_parser.pain002_parser import (
    correlate_with_results,
    parse_pain002_files,
)
from src.payment_types import get_handler
from src.reporting.json_reporter import generate_json_report
from src.reporting.junit_reporter import generate_junit_report
from src.reporting.word_reporter import generate_word_report, generate_txt_report
from src.validation.bic_directory import load_bic_directory, reset_bic_directory
from src.validation.address_validator import convert_unstructured_to_structured
from src.validation.business_rules import (
    apply_rule_violation,
    validate_all_business_rules,
)
from src.validation.xsd_validator import XsdValidator
from src.xml_generator.bah_builder import wrap_with_bah
from src.xml_generator.pain001_builder import (
    build_pain001_document,
    build_pain001_xml,
    serialize_xml,
)


class PaymentTestPipeline:
    """Verarbeitet Testfälle und generiert XMLs, Validierungen und Reports.

    Verwendung:
        pipeline = PaymentTestPipeline(config, seed=42)
        results = pipeline.process(testcases, output_dir, verbose=True)
        pipeline.generate_reports(results, input_file, output_dir)
    """

    def __init__(self, config: AppConfig, seed: Optional[int] = None):
        self.config = config
        self.factory = DataFactory(seed=seed)
        self.xsd_validator = XsdValidator(
            config.xsd_path, cbpr_xsd_path=config.cbpr_xsd_path
        )
        # BIC-Verzeichnis laden (optional)
        if config.bic_directory_path:
            bic_dir = load_bic_directory(config.bic_directory_path)
            print(f"BIC-Verzeichnis geladen: {bic_dir.size} Einträge aus {config.bic_directory_path}")
        # Speichert Instructions für spätere pain.002-Korrelation
        self._instructions: Dict[str, PaymentInstruction] = {}

    def process(
        self,
        testcases: List[TestCase],
        output_dir: str,
        verbose: bool = False,
    ) -> List[TestCaseResult]:
        """Verarbeitet alle Testfälle (einzeln oder gruppiert)."""
        results = []
        groups = self._group_testcases(testcases)

        for group in groups:
            is_multi = group[0].group_id is not None and len(group) > 1

            if is_multi:
                group_results = self._process_group(group, output_dir, verbose)
            else:
                group_results = [
                    self._process_single(tc, output_dir, verbose)
                    for tc in group
                ]

            results.extend(group_results)

        return results

    def generate_reports(
        self,
        results: List[TestCaseResult],
        input_file: str,
        output_dir: str,
    ) -> Dict[str, str]:
        """Erzeugt alle Reports und gibt die Dateipfade zurück."""
        paths = {}

        paths["json"] = generate_json_report(results, input_file, output_dir)
        paths["junit"] = generate_junit_report(results, output_dir)

        if self.config.report_format == "docx":
            try:
                paths["docx"] = generate_word_report(results, input_file, output_dir)
            except Exception:
                paths["txt"] = generate_txt_report(results, input_file, output_dir)
        else:
            paths["txt"] = generate_txt_report(results, input_file, output_dir)

        return paths

    # ----- Internal: Instruction Building -----

    def build_instruction(
        self, testcase: TestCase
    ) -> Tuple[PaymentInstruction, TestCase]:
        """Baut eine PaymentInstruction aus einem Testfall.

        Wendet Defaults, Overrides und Violations an.
        Raises ValueError bei Mapping-Fehlern.
        """
        testcase = self._apply_defaults(testcase)

        mapped, special, mapping_errors = validate_and_map_overrides(testcase.overrides)
        warnings = [e for e in mapping_errors if e.is_warning]
        hard_errors = [e for e in mapping_errors if not e.is_warning]
        if hard_errors:
            raise ValueError(
                "Mapping-Fehler: " + "; ".join(e.message for e in hard_errors)
            )
        for w in warnings:
            print(f"  Warnung: {w.message}")

        handler = get_handler(testcase.payment_type)
        transactions = handler.generate_transactions(testcase, self.factory)

        # Testcase-Level C-Level-Overrides (RgltryRptg auf alle Transaktionen)
        transactions = self._apply_testcase_c_level_overrides(mapped, transactions)

        # Per-Transaction C-Level-Overrides (F-13)
        transactions = self._apply_c_level_overrides(testcase, transactions)

        # CGI-MP: Auto-Konversion unstrukturierter Adressen zu strukturiert
        if testcase.standard == Standard.CGI_MP:
            transactions = self._convert_cgi_mp_addresses(transactions)

        # SIC5 Instant: ServiceLevel und LocalInstrument setzen
        service_level = handler.get_service_level()
        local_instrument = None
        if testcase.instant:
            service_level = "INST"
            local_instrument = "INST"

        instruction = PaymentInstruction(
            msg_id=self.factory.generate_msg_id(),
            pmt_inf_id=self.factory.generate_pmt_inf_id(),
            cre_dt_tm=datetime.now().isoformat(),
            reqd_exctn_dt=self.factory.get_next_business_day(testcase.payment_type).isoformat(),
            debtor=testcase.debtor,
            service_level=service_level,
            local_instrument=local_instrument,
            batch_booking=testcase.batch_booking,
            charge_bearer=handler.get_charge_bearer(),
            transactions=transactions,
        )

        # B-Level Overrides
        instruction = self._apply_b_level_overrides(instruction, mapped)

        # Negative Testing
        if testcase.violate_rule:
            instruction = apply_rule_violation(testcase, instruction)

        return instruction, testcase

    # ----- Internal: Processing -----

    def _process_single(
        self, testcase: TestCase, output_dir: str, verbose: bool
    ) -> TestCaseResult:
        """Verarbeitet einen einzelnen Testfall."""
        try:
            instruction, testcase = self.build_instruction(testcase)
        except ValueError as e:
            return self._error_result(testcase, str(e))

        self._instructions[testcase.testcase_id] = instruction

        xml_doc = build_pain001_xml(instruction, standard=testcase.standard)
        self._assert_xsd_valid(xml_doc, testcase)

        # CBPR+: BAH (Business Application Header) hinzufuegen
        save_doc = xml_doc
        if testcase.standard == Standard.CBPR_PLUS_2026:
            save_doc = self._wrap_cbpr_with_bah(xml_doc, instruction)

        xml_path = self._save_xml(save_doc, testcase.testcase_id, output_dir)
        if verbose:
            print(f"  XML gespeichert: {xml_path}")

        return self._evaluate(testcase, instruction, xml_path)

    def _process_group(
        self, testcases: List[TestCase], output_dir: str, verbose: bool
    ) -> List[TestCaseResult]:
        """Verarbeitet eine Gruppe (N Testfälle → 1 XML mit N PmtInf)."""
        built: List[Tuple[TestCase, PaymentInstruction]] = []
        results: List[TestCaseResult] = []

        for tc in testcases:
            try:
                instr, tc = self.build_instruction(tc)
                built.append((tc, instr))
            except ValueError as e:
                results.append(self._error_result(tc, str(e)))

        if not built:
            return results

        group_id = testcases[0].group_id
        all_instructions = [instr for _, instr in built]
        first = all_instructions[0]

        document = Pain001Document(
            msg_id=first.msg_id,
            cre_dt_tm=first.cre_dt_tm,
            initiating_party_name=first.debtor.name,
            payment_instructions=all_instructions,
        )

        group_standard = testcases[0].standard
        xml_doc = build_pain001_document(document, standard=group_standard)

        xsd_valid, xsd_errors = self.xsd_validator.validate(xml_doc, standard=group_standard)
        if not xsd_valid:
            tc_ids = ", ".join(tc.testcase_id for tc, _ in built)
            error_detail = "\n".join(f"  - {err}" for err in xsd_errors)
            raise RuntimeError(
                f"XSD-Validierung fehlgeschlagen für Gruppe '{group_id}' "
                f"(Testfälle: {tc_ids}).\n{error_detail}"
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uuid_short = self.factory.generate_uuid_short()
        filename = f"{timestamp}_Group-{group_id}_{uuid_short}.xml"
        xml_path = os.path.join(output_dir, filename)
        with open(xml_path, "wb") as f:
            f.write(serialize_xml(xml_doc))

        if verbose:
            print(f"  XML gespeichert (Multi-Payment, {len(built)} PmtInf): {xml_path}")

        for tc, instr in built:
            self._instructions[tc.testcase_id] = instr
            results.append(self._evaluate(tc, instr, xml_path))

        return results

    # ----- pain.002 Response Processing -----

    def process_responses(
        self,
        pain002_paths: List[str],
        results: List[TestCaseResult],
        verbose: bool = False,
    ) -> Tuple[List[TestCaseResult], List[str]]:
        """Parst pain.002-Dateien und korreliert sie mit Testfall-Ergebnissen.

        Args:
            pain002_paths: Pfade zu pain.002 XML-Dateien
            results: Bestehende Testfall-Ergebnisse aus der Generierung
            verbose: Verbose-Ausgabe

        Returns:
            Tuple aus (aktualisierte Ergebnisse, Fehlermeldungen)
        """
        pain002_results, errors = parse_pain002_files(pain002_paths)

        if verbose:
            for p in pain002_results:
                print(
                    f"  pain.002 geparst: {p.pain002_file_path} "
                    f"(OrgnlMsgId={p.original_msg_id}, "
                    f"GrpSts={p.group_status or '-'})"
                )
            for e in errors:
                print(f"  Fehler: {e}")

        if not pain002_results:
            return results, errors

        updated = correlate_with_results(
            pain002_results, results, self._instructions
        )

        if verbose:
            matched = sum(1 for r in updated if r.pain002_result is not None)
            print(f"  {matched} von {len(updated)} Testfällen korreliert.")

        return updated, errors

    @property
    def instructions(self) -> Dict[str, PaymentInstruction]:
        """Zugriff auf gespeicherte Instructions (für pain.002-Korrelation)."""
        return dict(self._instructions)

    # ----- Internal: Helpers -----

    def _apply_defaults(self, testcase: TestCase) -> TestCase:
        updates = {}
        if testcase.payment_type is None:
            updates["payment_type"] = PaymentType.DOMESTIC_IBAN
        pt = updates.get("payment_type", testcase.payment_type)
        if testcase.debtor.name is None:
            updates["debtor"] = testcase.debtor.model_copy(
                update={"name": self.factory.generate_debtor_name()}
            )
        if testcase.currency is None:
            updates["currency"] = self.factory.generate_currency(pt)
        if testcase.amount is None:
            updates["amount"] = self.factory.generate_amount(pt, instant=testcase.instant)
        return testcase.model_copy(update=updates) if updates else testcase

    @staticmethod
    def _convert_cgi_mp_addresses(transactions):
        """Konvertiert unstrukturierte Creditor-Adressen zu strukturiert (CGI-MP).

        Bei CGI-MP sind nur strukturierte Adressen erlaubt. Diese Methode
        versucht, AdrLine-basierte Adressen automatisch in StrtNm/PstCd/TwnNm
        aufzuspalten.
        """
        updated = []
        for tx in transactions:
            if tx.creditor_address and "AdrLine" in tx.creditor_address:
                converted, success = convert_unstructured_to_structured(
                    tx.creditor_address
                )
                if success:
                    tx = tx.model_copy(update={"creditor_address": converted})
            updated.append(tx)
        return updated

    def _apply_b_level_overrides(
        self, instruction: PaymentInstruction, mapped: Dict
    ) -> PaymentInstruction:
        b_level_map = {
            "ChrgBr": "charge_bearer",
            "SvcLvl.Cd": "service_level",
            "LclInstrm.Cd": "local_instrument",
            "CtgyPurp.Cd": "category_purpose",
            "ReqdExctnDt": "reqd_exctn_dt",
        }
        # Boolean B-Level Overrides (Wert wird als true/false interpretiert)
        b_level_bool_map = {
            "BtchBookg": "batch_booking",
        }
        updates = {}
        debtor_updates = {}
        ultmt_dbtr_data = {}
        for key, info in mapped.items():
            if info["level"] == "B":
                if key in b_level_map:
                    updates[b_level_map[key]] = info["value"]
                elif key in b_level_bool_map:
                    updates[b_level_bool_map[key]] = info["value"].lower() in ("true", "1", "ja", "yes")
                elif key == "Dbtr.Id.OrgId.LEI":
                    debtor_updates["lei"] = info["value"]
                elif key == "UltmtDbtr.Nm":
                    ultmt_dbtr_data["Nm"] = info["value"]
                elif key.startswith("UltmtDbtr.PstlAdr."):
                    addr_key = key.split(".")[-1]
                    ultmt_dbtr_data[addr_key] = info["value"]
        if debtor_updates:
            updates["debtor"] = instruction.debtor.model_copy(update=debtor_updates)
        if ultmt_dbtr_data:
            existing = dict(instruction.ultimate_debtor or {})
            existing.update(ultmt_dbtr_data)
            updates["ultimate_debtor"] = existing
        return instruction.model_copy(update=updates) if updates else instruction

    def _apply_testcase_c_level_overrides(self, mapped, transactions):
        """Wendet Testcase-Level C-Level-Overrides auf alle Transaktionen an.

        Betrifft RgltryRptg-, TaxRmt-, UltmtCdtr- und UltmtDbtr-Keys,
        die auf Testcase-Ebene gesetzt werden und für alle Transaktionen gelten.
        """
        reg_data = {}
        tax_data = {}
        ultmt_cdtr_data = {}
        ultmt_dbtr_data = {}
        for key, info in mapped.items():
            if info["level"] == "C" and key.startswith("RgltryRptg."):
                reg_key = key[len("RgltryRptg."):]
                reg_data[reg_key] = info["value"]
            elif info["level"] == "C" and key.startswith("TaxRmt."):
                tax_key = key[len("TaxRmt."):]
                tax_data[tax_key] = info["value"]
            elif info["level"] == "C" and key.startswith("UltmtCdtr."):
                cdtr_key = key[len("UltmtCdtr."):]
                # PstlAdr.StrtNm → StrtNm
                if cdtr_key.startswith("PstlAdr."):
                    cdtr_key = cdtr_key[len("PstlAdr."):]
                ultmt_cdtr_data[cdtr_key] = info["value"]
            elif info["level"] == "C" and key.startswith("CdtTrfTxInf.UltmtDbtr."):
                dbtr_key = key[len("CdtTrfTxInf.UltmtDbtr."):]
                if dbtr_key.startswith("PstlAdr."):
                    dbtr_key = dbtr_key[len("PstlAdr."):]
                ultmt_dbtr_data[dbtr_key] = info["value"]
        if reg_data or tax_data or ultmt_cdtr_data or ultmt_dbtr_data:
            updated = []
            for tx in transactions:
                updates = {}
                if reg_data:
                    existing = dict(tx.regulatory_reporting or {})
                    existing.update(reg_data)
                    updates["regulatory_reporting"] = existing
                if tax_data:
                    existing = dict(tx.tax_remittance or {})
                    existing.update(tax_data)
                    updates["tax_remittance"] = existing
                if ultmt_cdtr_data:
                    existing = dict(tx.ultimate_creditor or {})
                    existing.update(ultmt_cdtr_data)
                    updates["ultimate_creditor"] = existing
                if ultmt_dbtr_data:
                    existing = dict(tx.ultimate_debtor or {})
                    existing.update(ultmt_dbtr_data)
                    updates["ultimate_debtor"] = existing
                updated.append(tx.model_copy(update=updates) if updates else tx)
            return updated
        return transactions

    def _apply_c_level_overrides(self, testcase: TestCase, transactions):
        tx_inputs = testcase.transaction_inputs or []
        for i, tx in enumerate(transactions):
            if i < len(tx_inputs) and tx_inputs[i].overrides:
                tx_mapped, _, tx_errors = validate_and_map_overrides(tx_inputs[i].overrides)
                tx_warnings = [e for e in tx_errors if e.is_warning]
                tx_hard_errors = [e for e in tx_errors if not e.is_warning]
                if tx_hard_errors:
                    raise ValueError(
                        f"Mapping-Fehler in Transaktion {i+1}: "
                        + "; ".join(e.message for e in tx_hard_errors)
                    )
                for w in tx_warnings:
                    print(f"  Warnung (Transaktion {i+1}): {w.message}")
                updates = {}
                for key, info in tx_mapped.items():
                    if info["level"] == "C":
                        if key == "Cdtr.Nm":
                            updates["creditor_name"] = info["value"]
                        elif key == "CdtrAcct.IBAN":
                            updates["creditor_iban"] = info["value"]
                        elif key == "CdtrAgt.BICFI":
                            updates["creditor_bic"] = info["value"]
                        elif key == "RmtInf.Ustrd":
                            updates["remittance_info"] = {"type": "USTRD", "value": info["value"]}
                        elif key == "Purp.Cd":
                            updates["purpose_code"] = info["value"]
                        elif key == "Cdtr.Id.OrgId.LEI":
                            updates["creditor_lei"] = info["value"]
                        elif key.startswith("Cdtr.PstlAdr."):
                            addr_key = key.split(".")[-1]
                            addr = dict(tx.creditor_address or {})
                            addr[addr_key] = info["value"]
                            updates["creditor_address"] = addr
                        elif key.startswith("RgltryRptg."):
                            reg = dict(updates.get("regulatory_reporting") or tx.regulatory_reporting or {})
                            # Map dot-notation key to dict key: RgltryRptg.X.Y → X.Y
                            reg_key = key[len("RgltryRptg."):]
                            reg[reg_key] = info["value"]
                            updates["regulatory_reporting"] = reg
                        elif key.startswith("TaxRmt."):
                            tax = dict(updates.get("tax_remittance") or tx.tax_remittance or {})
                            tax_key = key[len("TaxRmt."):]
                            tax[tax_key] = info["value"]
                            updates["tax_remittance"] = tax
                        elif key.startswith("UltmtCdtr."):
                            cdtr = dict(updates.get("ultimate_creditor") or tx.ultimate_creditor or {})
                            cdtr_key = key[len("UltmtCdtr."):]
                            if cdtr_key.startswith("PstlAdr."):
                                cdtr_key = cdtr_key[len("PstlAdr."):]
                            cdtr[cdtr_key] = info["value"]
                            updates["ultimate_creditor"] = cdtr
                        elif key.startswith("CdtTrfTxInf.UltmtDbtr."):
                            dbtr = dict(updates.get("ultimate_debtor") or tx.ultimate_debtor or {})
                            dbtr_key = key[len("CdtTrfTxInf.UltmtDbtr."):]
                            if dbtr_key.startswith("PstlAdr."):
                                dbtr_key = dbtr_key[len("PstlAdr."):]
                            dbtr[dbtr_key] = info["value"]
                            updates["ultimate_debtor"] = dbtr
                if updates:
                    transactions[i] = tx.model_copy(update=updates)
        return transactions

    def _evaluate(
        self, testcase: TestCase, instruction: PaymentInstruction, xml_path: str
    ) -> TestCaseResult:
        br_results = validate_all_business_rules(instruction, testcase)
        all_passed = all(r.passed for r in br_results)

        if testcase.expected_result == ExpectedResult.OK:
            overall_pass = all_passed
        else:
            overall_pass = not all_passed

        return TestCaseResult(
            testcase_id=testcase.testcase_id,
            titel=testcase.titel,
            payment_type=testcase.payment_type,
            expected_result=testcase.expected_result,
            xsd_valid=True,
            business_rule_results=br_results,
            overall_pass=overall_pass,
            xml_file_path=xml_path,
            remarks=testcase.remarks,
        )

    def _assert_xsd_valid(self, xml_doc, testcase: TestCase):
        valid, errors = self.xsd_validator.validate(xml_doc, standard=testcase.standard)
        if not valid:
            detail = "\n".join(f"  - {e}" for e in errors)
            raise RuntimeError(
                f"XSD-Validierung fehlgeschlagen für {testcase.testcase_id} "
                f"({testcase.payment_type.value}, {testcase.standard.value}). "
                f"Bug im XML-Generator.\n{detail}"
            )

    @staticmethod
    def _wrap_cbpr_with_bah(
        xml_doc: etree._Element, instruction: PaymentInstruction
    ) -> etree._Element:
        """Wraps a CBPR+ pain.001 Document with a Business Application Header."""
        from_bic = instruction.debtor.bic or "NOTPROVIDED"
        to_bic = instruction.transactions[0].creditor_bic if instruction.transactions else "NOTPROVIDED"
        return wrap_with_bah(
            pain001_doc=xml_doc,
            from_bic=from_bic,
            to_bic=to_bic or "NOTPROVIDED",
            msg_id=instruction.msg_id,
            cre_dt=instruction.cre_dt_tm,
        )

    def _save_xml(self, xml_doc, testcase_id: str, output_dir: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uuid_short = self.factory.generate_uuid_short()
        filename = f"{timestamp}_{testcase_id}_{uuid_short}.xml"
        path = os.path.join(output_dir, filename)
        with open(path, "wb") as f:
            f.write(serialize_xml(xml_doc))
        return path

    @staticmethod
    def _error_result(testcase: TestCase, message: str) -> TestCaseResult:
        return TestCaseResult(
            testcase_id=testcase.testcase_id,
            titel=testcase.titel,
            payment_type=testcase.payment_type or PaymentType.DOMESTIC_IBAN,
            expected_result=testcase.expected_result,
            xsd_valid=False,
            xsd_errors=[message],
            overall_pass=False,
            remarks=message,
        )

    @staticmethod
    def _group_testcases(testcases: List[TestCase]) -> List[List[TestCase]]:
        groups: Dict[Optional[str], List[TestCase]] = {}
        for tc in testcases:
            key = tc.group_id
            if key not in groups:
                groups[key] = []
            groups[key].append(tc)
        return list(groups.values())
