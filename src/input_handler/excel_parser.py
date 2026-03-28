"""Excel-Parser v2: Liest Testfälle mit separaten Transaktionszeilen."""

from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple

from openpyxl import load_workbook

from src.mapping.field_mapper import parse_key_value_pairs
from src.models.testcase import (
    DebtorInfo,
    ExpectedResult,
    PaymentType,
    Standard,
    TestCase,
    TransactionInput,
)

# Pflicht-Spalten (muessen im Header vorhanden sein)
REQUIRED_COLUMNS = [
    "TestcaseID",
    "Titel",
    "Ziel",
    "Erwartetes Ergebnis",
    "Debtor IBAN",
]

VALID_PAYMENT_TYPES = {pt.value for pt in PaymentType}
VALID_EXPECTED_RESULTS = {er.value for er in ExpectedResult}


def _parse_amount(raw, testcase_id: str = "", errors: list = None) -> Optional[Decimal]:
    """Parst einen Betrag, gibt None bei leerem Input zurück.

    Negative/Null-Betraege erzeugen eine Warnung statt stiller None-Rueckgabe.
    """
    if raw is None or str(raw).strip() == "":
        return None
    try:
        val = Decimal(str(raw))
        if val <= 0:
            if errors is not None:
                errors.append(
                    f"Testfall '{testcase_id}': Betrag '{raw}' ist nicht positiv."
                )
            return None
        return val
    except (InvalidOperation, TypeError, ValueError):
        if errors is not None:
            errors.append(
                f"Testfall '{testcase_id}': Betrag '{raw}' ist keine gültige Zahl."
            )
        return None


def _str_or_none(val) -> Optional[str]:
    """Gibt einen getrimmten String oder None zurück."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _parse_transaction_input(row, col_index) -> TransactionInput:
    """Liest Transaktions-Daten aus einer Zeile."""

    def cell(col_name):
        idx = col_index.get(col_name)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    overrides_raw = _str_or_none(cell("Weitere Testdaten"))
    overrides = {}
    if overrides_raw:
        overrides = parse_key_value_pairs(overrides_raw)

    return TransactionInput(
        amount=_parse_amount(cell("Betrag")),
        currency=_str_or_none(cell("Währung")),
        creditor_name=_str_or_none(cell("Creditor Name")),
        creditor_iban=_str_or_none(cell("Creditor IBAN")),
        creditor_bic=_str_or_none(cell("Creditor BIC")),
        remittance_info=_str_or_none(cell("Verwendungszweck")),
        overrides=overrides,
    )


def parse_excel(file_path: str) -> Tuple[List[TestCase], List[str]]:
    """Liest und validiert eine Excel-Datei mit Testfällen (v2-Format).

    Zeilen mit TestcaseID = neuer Testfall.
    Zeilen ohne TestcaseID = zusaetzliche Transaktion zum vorherigen Testfall.

    Returns:
        Tuple von (testcases, errors). Bei Fehlern ist testcases leer.
    """
    errors = []

    try:
        wb = load_workbook(file_path, read_only=True, data_only=True)
    except Exception as e:
        return [], [f"Excel-Datei konnte nicht geöffnet werden: {e}"]

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    if not rows:
        return [], ["Die Excel-Datei ist leer."]

    # Header-Zeile validieren
    header = [str(cell).strip() if cell else "" for cell in rows[0]]

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in header]
    if missing_columns:
        return [], [
            f"Fehlende Pflichtspalten: {', '.join(missing_columns)}. "
            f"Erwartet mindestens: {', '.join(REQUIRED_COLUMNS)}"
        ]

    col_index = {name: i for i, name in enumerate(header)}

    def cell_val(row, col_name):
        idx = col_index.get(col_name)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    # Datenzeilen verarbeiten
    testcases = []
    current_tc = None
    seen_ids = set()

    for row in rows[1:]:
        testcase_id = _str_or_none(cell_val(row, "TestcaseID"))

        if testcase_id:
            # === Neue Testfall-Zeile ===
            if current_tc is not None:
                testcases.append(current_tc)

            row_errors = []

            # Duplikat-Erkennung
            if testcase_id in seen_ids:
                row_errors.append(
                    f"Testfall '{testcase_id}': TestcaseID ist doppelt vorhanden."
                )
            seen_ids.add(testcase_id)

            titel = _str_or_none(cell_val(row, "Titel"))
            if not titel:
                row_errors.append(f"Testfall '{testcase_id}': 'Titel' fehlt.")
                titel = testcase_id

            ziel = _str_or_none(cell_val(row, "Ziel"))
            if not ziel:
                row_errors.append(f"Testfall '{testcase_id}': 'Ziel' fehlt.")
                ziel = ""

            expected_raw = _str_or_none(cell_val(row, "Erwartetes Ergebnis"))
            if not expected_raw or expected_raw not in VALID_EXPECTED_RESULTS:
                row_errors.append(
                    f"Testfall '{testcase_id}': 'Erwartetes Ergebnis' muss 'OK' oder 'NOK' sein, "
                    f"ist aber '{expected_raw}'."
                )
                errors.extend(row_errors)
                current_tc = None
                continue
            expected_result = ExpectedResult(expected_raw)

            debtor_iban = _str_or_none(cell_val(row, "Debtor IBAN"))
            if not debtor_iban:
                row_errors.append(f"Testfall '{testcase_id}': 'Debtor IBAN' fehlt.")
                errors.extend(row_errors)
                current_tc = None
                continue

            if row_errors:
                errors.extend(row_errors)

            # Optionale Felder
            payment_type_raw = _str_or_none(cell_val(row, "Zahlungstyp"))
            payment_type = None
            if payment_type_raw:
                if payment_type_raw in VALID_PAYMENT_TYPES:
                    payment_type = PaymentType(payment_type_raw)
                else:
                    errors.append(
                        f"Testfall '{testcase_id}': Ungültiger Zahlungstyp '{payment_type_raw}'. "
                        f"Gültig: {', '.join(VALID_PAYMENT_TYPES)}"
                    )
                    current_tc = None
                    continue

            debtor_name = _str_or_none(cell_val(row, "Debtor Name"))
            debtor_bic = _str_or_none(cell_val(row, "Debtor BIC"))

            debtor = DebtorInfo(
                name=debtor_name,
                iban=debtor_iban,
                bic=debtor_bic,
            )

            violate_rule = _str_or_none(cell_val(row, "ViolateRule"))

            overrides_raw = _str_or_none(cell_val(row, "Weitere Testdaten"))
            overrides = {}
            group_id = None
            if overrides_raw:
                overrides = parse_key_value_pairs(overrides_raw)
                if "ViolateRule" in overrides:
                    violate_rule = violate_rule or overrides.pop("ViolateRule")
                if "GroupId" in overrides:
                    group_id = overrides.pop("GroupId")

            # Standard (optional)
            standard_raw = _str_or_none(cell_val(row, "Standard"))
            standard = Standard.SPS_2025
            if standard_raw:
                standard_lower = standard_raw.lower().strip()
                valid_standards = {s.value: s for s in Standard}
                if standard_lower in valid_standards:
                    standard = valid_standards[standard_lower]
                else:
                    errors.append(
                        f"Testfall '{testcase_id}': Ungültiger Standard '{standard_raw}'. "
                        f"Gültig: {', '.join(valid_standards.keys())}"
                    )
                    current_tc = None
                    continue

            first_tx = _parse_transaction_input(row, col_index)

            current_tc = TestCase(
                testcase_id=testcase_id,
                titel=titel,
                ziel=ziel,
                expected_result=expected_result,
                payment_type=payment_type,
                amount=first_tx.amount,
                currency=first_tx.currency,
                debtor=debtor,
                overrides=overrides,
                violate_rule=violate_rule,
                transaction_inputs=[first_tx],
                standard=standard,
                group_id=group_id,
                expected_api_response=_str_or_none(cell_val(row, "Erwartete API-Antwort")) or "",
                remarks=_str_or_none(cell_val(row, "Bemerkungen")) or "",
            )

        else:
            # === Transaktionszeile (kein TestcaseID) ===
            if current_tc is None:
                continue

            tx_input = _parse_transaction_input(row, col_index)
            current_tc.transaction_inputs.append(tx_input)

    if current_tc is not None:
        testcases.append(current_tc)

    wb.close()

    if errors:
        return [], errors

    return testcases, []
