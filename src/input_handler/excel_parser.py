"""Excel-Parser: Liest Testfälle aus einer .xlsx-Datei."""

from decimal import Decimal, InvalidOperation
from typing import List, Tuple

from openpyxl import load_workbook

from src.mapping.field_mapper import parse_key_value_pairs
from src.models.testcase import (
    DebtorInfo,
    ExpectedResult,
    PaymentType,
    TestCase,
)

REQUIRED_COLUMNS = [
    "TestcaseID",
    "Titel",
    "Ziel",
    "Erwartetes Ergebnis",
    "Zahlungstyp",
    "Betrag",
    "Währung",
    "Debtor Infos",
    "Weitere Testdaten",
    "Erwartete API-Antwort",
    "Ergebnis (OK/NOK)",
    "Bemerkungen",
]

VALID_PAYMENT_TYPES = {pt.value for pt in PaymentType}
VALID_EXPECTED_RESULTS = {er.value for er in ExpectedResult}


def _parse_debtor_info(debtor_text: str, testcase_id: str) -> Tuple[DebtorInfo, List[str]]:
    """Parst Debtor-Infos aus Key=Value-Format."""
    errors = []
    pairs = parse_key_value_pairs(debtor_text)

    if "Name" not in pairs:
        errors.append(
            f"Testfall '{testcase_id}': Pflichtfeld 'Name' fehlt in 'Debtor Infos'."
        )
    if "IBAN" not in pairs:
        errors.append(
            f"Testfall '{testcase_id}': Pflichtfeld 'IBAN' fehlt in 'Debtor Infos'."
        )

    if errors:
        return None, errors

    return DebtorInfo(
        name=pairs["Name"],
        iban=pairs["IBAN"],
        bic=pairs.get("BIC"),
        street=pairs.get("Strasse"),
        building=pairs.get("Hausnummer"),
        postal_code=pairs.get("PLZ"),
        town=pairs.get("Ort"),
        country=pairs.get("Land", "CH"),
    ), errors


def parse_excel(file_path: str) -> Tuple[List[TestCase], List[str]]:
    """Liest und validiert eine Excel-Datei mit Testfällen.

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
    missing_columns = []
    for col in REQUIRED_COLUMNS:
        if col not in header:
            missing_columns.append(col)

    if missing_columns:
        return [], [
            f"Fehlende Pflichtspalten: {', '.join(missing_columns)}. "
            f"Erwartet: {', '.join(REQUIRED_COLUMNS)}"
        ]

    col_index = {name: i for i, name in enumerate(header)}

    # Datenzeilen verarbeiten
    testcases = []
    for row_num, row in enumerate(rows[1:], start=2):
        if row_num == 1:
            continue

        def cell(col_name):
            idx = col_index.get(col_name)
            if idx is None or idx >= len(row):
                return None
            return row[idx]

        testcase_id = cell("TestcaseID")
        if not testcase_id:
            continue  # Zeilen ohne TestcaseID überspringen (FR-03)

        testcase_id = str(testcase_id).strip()
        row_errors = []

        # Titel
        titel = cell("Titel")
        if not titel:
            row_errors.append(f"Testfall '{testcase_id}': 'Titel' fehlt.")
        else:
            titel = str(titel).strip()

        # Ziel
        ziel = cell("Ziel")
        if not ziel:
            row_errors.append(f"Testfall '{testcase_id}': 'Ziel' fehlt.")
        else:
            ziel = str(ziel).strip()

        # Erwartetes Ergebnis
        expected = cell("Erwartetes Ergebnis")
        if not expected or str(expected).strip() not in VALID_EXPECTED_RESULTS:
            row_errors.append(
                f"Testfall '{testcase_id}': 'Erwartetes Ergebnis' muss 'OK' oder 'NOK' sein, "
                f"ist aber '{expected}'."
            )
            expected_result = None
        else:
            expected_result = ExpectedResult(str(expected).strip())

        # Zahlungstyp
        payment_type_raw = cell("Zahlungstyp")
        if not payment_type_raw or str(payment_type_raw).strip() not in VALID_PAYMENT_TYPES:
            row_errors.append(
                f"Testfall '{testcase_id}': 'Zahlungstyp' muss einer von "
                f"{', '.join(VALID_PAYMENT_TYPES)} sein, ist aber '{payment_type_raw}'."
            )
            payment_type = None
        else:
            payment_type = PaymentType(str(payment_type_raw).strip())

        # Betrag
        amount_raw = cell("Betrag")
        try:
            amount = Decimal(str(amount_raw))
            if amount <= 0:
                row_errors.append(
                    f"Testfall '{testcase_id}': 'Betrag' muss größer als 0 sein."
                )
        except (InvalidOperation, TypeError, ValueError):
            row_errors.append(
                f"Testfall '{testcase_id}': 'Betrag' ist keine gültige Zahl: '{amount_raw}'."
            )
            amount = None

        # Währung
        currency = cell("Währung")
        if not currency:
            row_errors.append(f"Testfall '{testcase_id}': 'Währung' fehlt.")
        else:
            currency = str(currency).strip().upper()

        # Debtor Infos
        debtor_raw = cell("Debtor Infos")
        if not debtor_raw:
            row_errors.append(f"Testfall '{testcase_id}': 'Debtor Infos' fehlt.")
            debtor = None
        else:
            debtor, debtor_errors = _parse_debtor_info(str(debtor_raw), testcase_id)
            row_errors.extend(debtor_errors)

        # Weitere Testdaten (optional)
        overrides_raw = cell("Weitere Testdaten")
        overrides = {}
        violate_rule = None
        tx_count = 1
        group_id = None
        if overrides_raw:
            overrides = parse_key_value_pairs(str(overrides_raw))
            if "ViolateRule" in overrides:
                violate_rule = overrides.pop("ViolateRule")
            if "GroupId" in overrides:
                group_id = overrides.pop("GroupId")
            if "TxCount" in overrides:
                try:
                    tx_count = int(overrides.pop("TxCount"))
                    if tx_count < 1:
                        row_errors.append(
                            f"Testfall '{testcase_id}': 'TxCount' muss >= 1 sein."
                        )
                        tx_count = 1
                except ValueError:
                    row_errors.append(
                        f"Testfall '{testcase_id}': 'TxCount' ist keine gültige Zahl."
                    )

        if row_errors:
            errors.extend(row_errors)
            continue

        testcases.append(TestCase(
            testcase_id=testcase_id,
            titel=titel,
            ziel=ziel,
            expected_result=expected_result,
            payment_type=payment_type,
            amount=amount,
            currency=currency,
            debtor=debtor,
            overrides=overrides,
            violate_rule=violate_rule,
            tx_count=tx_count,
            group_id=group_id,
            expected_api_response=str(cell("Erwartete API-Antwort") or ""),
            remarks=str(cell("Bemerkungen") or ""),
        ))

    wb.close()

    if errors:
        return [], errors

    return testcases, []
