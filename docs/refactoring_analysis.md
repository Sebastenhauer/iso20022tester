# Refactoring-Analyse: Was würde ich anders bauen?

**Datum:** 28. März 2026
**Branch:** claude2_feature
**Basis:** Codebase-Stand nach 69dc8f5 (main)

---

## Zusammenfassung

Das Projekt ist funktional und liefert korrekte Ergebnisse (65 Testfälle, 59 XMLs, alle XSD-valide). Die Architektur hat aber **Wachstumsschmerzen** — Entscheidungen, die bei 8 Testfällen sinnvoll waren, skalieren nicht gut auf 65+ Testfälle, 4 Standards und 40+ Business Rules.

Die 5 grössten Probleme:

| # | Problem | Auswirkung |
|---|---------|-----------|
| 1 | `main.py` ist ein 511-Zeilen-Monolith | Nicht testbar, schwer erweiterbar |
| 2 | Payment-Handler duplizieren ~200 Zeilen | Jede Änderung muss 4x gemacht werden |
| 3 | `TestCase`-Modell mischt Concerns | 14 Felder, davon 4 die woanders hingehören |
| 4 | Business Rules über 3 Dateien verstreut | Eine Regel verstehen erfordert 3 Files |
| 5 | ~9.5% Test-Coverage | Refactoring ohne Netz |

---

## 1. main.py — Pipeline statt Script

### Problem

`main.py` (511 Zeilen) macht alles: Defaults, Override-Mapping, Transaktionsgenerierung, XML-Bau, XSD-Validierung, Business Rules, Pass/Fail, Reporting. Die Funktion `_build_instruction()` allein ist 99 Zeilen mit 7 verschiedenen Verantwortlichkeiten.

Ausserdem sind `_process_single_testcase()` und `_process_group()` zu ~90% identisch.

### Was ich anders bauen würde

Ein `PaymentTestPipeline`-Objekt mit klar getrennten Schritten:

```python
class PaymentTestPipeline:
    def __init__(self, config: AppConfig):
        self.factory = DataFactory(config.seed)
        self.xsd_validator = XsdValidator(config.xsd_path, config.cbpr_xsd_path)

    def run(self, testcases: List[TestCase]) -> List[TestCaseResult]:
        groups = self._group(testcases)
        return [self._process(g) for g in groups]

    def _process(self, group: List[TestCase]) -> List[TestCaseResult]:
        instructions = [InstructionBuilder(self.factory).build(tc) for tc in group]
        xml = XmlRenderer(group[0].standard).render(instructions)
        self._validate_xsd(xml, group[0].standard)
        rules = [self._validate_rules(instr, tc) for instr, tc in zip(instructions, group)]
        return [self._evaluate(tc, r) for tc, r in zip(group, rules)]
```

**Gewinn:** Jeder Schritt ist einzeln testbar. Gruppierung und Einzelverarbeitung nutzen denselben Code.

---

## 2. Payment-Handler — TransactionBuilder statt Copy-Paste

### Problem

Alle 4 Handler (`sepa.py`, `domestic_qr.py`, `domestic_iban.py`, `cbpr_plus.py`) haben nahezu identische `generate_transactions()`-Methoden. Das Pattern ist immer:

```python
creditor_iban = (tx_input.creditor_iban if tx_input else None) \
    or testcase.overrides.get("CdtrAcct.IBAN") \
    or factory.generate_creditor_iban(self.payment_type)
```

Das gleiche für `creditor_name`, `creditor_bic`, `amount`, `currency` — in jedem Handler einzeln.

**~200 Zeilen duplizierter Code** über 4 Dateien.

### Was ich anders bauen würde

Ein `TransactionBuilder` in `base.py`, der die Fallback-Kette einmal implementiert:

```python
class TransactionBuilder:
    def __init__(self, factory: DataFactory, testcase: TestCase, payment_type: PaymentType):
        self.factory = factory
        self.testcase = testcase
        self.payment_type = payment_type

    def build(self, tx_input: Optional[TransactionInput]) -> Transaction:
        return Transaction(
            end_to_end_id=self.factory.generate_end_to_end_id(),
            amount=self._resolve(tx_input, "amount", self.factory.generate_amount),
            currency=self._resolve(tx_input, "currency", self.factory.generate_currency),
            creditor_iban=self._resolve(tx_input, "creditor_iban", self.factory.generate_creditor_iban),
            creditor_name=self._resolve(tx_input, "creditor_name", self.factory.generate_creditor_name),
            # ...
        )

    def _resolve(self, tx_input, field, generator_fn):
        """tx_input → override → generate"""
        return (getattr(tx_input, field, None) if tx_input else None) \
            or self.testcase.overrides.get(FIELD_TO_OVERRIDE_KEY[field]) \
            or generator_fn(self.payment_type)
```

Handler würden nur noch typ-spezifische Abweichungen definieren (z.B. SEPA Name max 70 Zeichen, QR-Referenz generieren).

**Gewinn:** ~200 Zeilen weniger, eine Stelle für die Fallback-Logik.

---

## 3. TestCase-Modell — Concerns trennen

### Problem

`TestCase` hat 14 Felder die 3 verschiedene Dinge beschreiben:

| Concern | Felder | Gehört in... |
|---------|--------|-------------|
| **Zahlungsdaten** | debtor, payment_type, standard, amount, currency | `PaymentSpec` |
| **Testkontext** | testcase_id, titel, ziel, expected_result, violate_rule, remarks | `TestCase` |
| **Orchestrierung** | group_id, tx_count, transaction_inputs | `TestCase` |
| **Nicht verwendet** | expected_api_response | Entfernen |

Ausserdem: `amount` und `currency` existieren sowohl auf TestCase-Ebene als auch in `TransactionInput` — unklar welches Vorrang hat.

### Was ich anders bauen würde

```python
class TestCase(BaseModel):
    # Testkontext
    testcase_id: str
    titel: str
    ziel: str
    expected_result: ExpectedResult
    violate_rule: Optional[str] = None
    remarks: Optional[str] = None
    group_id: Optional[str] = None

    # Zahlungsdaten
    debtor: DebtorInfo
    payment_type: Optional[PaymentType] = None
    standard: Standard = Standard.SPS_2025
    transactions: List[TransactionSpec] = []  # Ersetzt transaction_inputs + amount/currency
    overrides: Dict[str, str] = {}
```

`amount` und `currency` nur noch in `TransactionSpec` — eine Single Source of Truth.

---

## 4. Business Rules — Rule Registry statt 3-Datei-Verteilung

### Problem

Um eine einzelne Regel (z.B. BR-SEPA-001) zu verstehen, muss man 3 Dateien lesen:

| Was | Wo | Zeilen |
|-----|-----|--------|
| Metadaten (ID, Beschreibung, Spec-Referenz) | `rule_catalog.py` | ~6 Zeilen |
| Validierungslogik | `sepa.py` (im Handler) | ~5 Zeilen |
| Violation-Logik | `business_rules.py` | ~5 Zeilen + Dict-Eintrag |

Neue Regel hinzufügen = 3 Dateien editieren + Dict aktualisieren.

### Was ich anders bauen würde

Eine Rule Registry, in der alles zusammen ist:

```python
@rule(
    id="BR-SEPA-001",
    category="SEPA",
    description="Waehrung muss EUR sein",
    spec_reference="SPS 2025 §3.15 Typ S",
    applies_to=(PaymentType.SEPA,),
    violatable=True,
)
def br_sepa_001(instruction: PaymentInstruction, testcase: TestCase) -> ValidationResult:
    for tx in instruction.transactions:
        if tx.currency != "EUR":
            return fail(f"Waehrung ist '{tx.currency}'")
    return pass_()

@br_sepa_001.violation
def _violate(instruction: PaymentInstruction) -> PaymentInstruction:
    txs = [tx.model_copy(update={"currency": "CHF"}) for tx in instruction.transactions]
    return instruction.model_copy(update={"transactions": txs})
```

**Gewinn:** Neue Regel = 1 Datei, 1 Stelle. Metadaten, Validierung und Violation zusammen.

---

## 5. XML-Generator — Strategy Pattern für Standards

### Problem

Standard-abhängige Logik ist in `pain001_builder.py` über if/else verstreut:

- Zeile 100-101: UTC-Konvertierung nur für CBPR+
- Zeile 104-105: PmtInfId = MsgId nur für CBPR+
- Zeile 141-147: NbOfTxs/CtrlSum Konditionale

Jeder neue Standard (z.B. EPC SEPA, SWIFT gpi) erfordert mehr if/else.

### Was ich anders bauen würde

```python
class StandardStrategy(ABC):
    def prepare_cre_dt_tm(self, cre_dt_tm: str) -> str: ...
    def prepare_pmt_inf_id(self, pmt_inf_id: str, msg_id: str) -> str: ...
    def grp_hdr_nb_of_txs(self, all_txs: List[Transaction]) -> str: ...
    def grp_hdr_ctrl_sum(self, all_txs: List[Transaction]) -> Optional[str]: ...

class Sps2025Strategy(StandardStrategy):
    def grp_hdr_nb_of_txs(self, all_txs): return str(len(all_txs))
    def grp_hdr_ctrl_sum(self, all_txs): return str(sum(tx.amount for tx in all_txs))

class CbprPlus2026Strategy(StandardStrategy):
    def grp_hdr_nb_of_txs(self, all_txs): return "1"
    def grp_hdr_ctrl_sum(self, all_txs): return None  # Kein CtrlSum
```

---

## 6. Override-Handling — Zentralisieren

### Problem

Override-Anwendung passiert an 3 verschiedenen Stellen:

1. **main.py:146-158** — B-Level Overrides (manuelles field-by-field if/elif)
2. **main.py:97-131** — C-Level per-Transaction Overrides (manuelles field-by-field)
3. **Payment-Handler** — Overrides in `generate_transactions()` via `testcase.overrides.get()`

### Was ich anders bauen würde

Ein `OverrideApplicator` der die Mapping-Tabelle nutzt:

```python
class OverrideApplicator:
    def apply_to_instruction(self, instruction: PaymentInstruction, overrides: MappedOverrides) -> PaymentInstruction:
        """Wendet alle B-Level Overrides an."""
        updates = {}
        for key, info in overrides.b_level.items():
            field = B_LEVEL_FIELD_MAP[key]  # z.B. "ChrgBr" → "charge_bearer"
            updates[field] = info.value
        return instruction.model_copy(update=updates)
```

Statt 40 Zeilen if/elif: eine generische Anwendungslogik basierend auf der Mapping-Tabelle.

---

## 7. Excel-Parser — Robustheit

### Probleme

- Negative Beträge werden still zu `None` (kein Fehler an User)
- Verwaiste Transaktionszeilen (vor erstem Testfall) werden still übersprungen
- Keine Duplikat-Erkennung für TestcaseIDs
- Keine Validierung von Sonderzeichen in TestcaseID
- Abgeschnittene Zeilen (fehlende Spalten) geben `None` statt Fehler

### Was ich anders bauen würde

Strikte Validierung mit sammelbaren Warnungen:

```python
@dataclass
class ParseWarning:
    row: int
    column: str
    message: str
    severity: Literal["error", "warning"]

def parse_excel(path: str) -> Tuple[List[TestCase], List[ParseWarning]]:
    warnings = []
    # ...
    if amount is not None and amount <= 0:
        warnings.append(ParseWarning(row=row_num, column="Betrag",
            message=f"Betrag {amount} ist negativ/null", severity="error"))
```

---

## 8. Test-Coverage — von 9.5% auf 70%

### Aktueller Stand

| Modul | Zeilen | Getestet | Coverage |
|-------|--------|----------|----------|
| main.py | 511 | 0 | 0% |
| payment_types/*.py | 464 | 0 | 0% |
| xml_generator/*.py | 382 | 0 | 0% |
| validation/business_rules.py | 430 | ~25% | ~25% |
| reporting/*.py | 223 | 0 | 0% |
| data_factory/*.py | 441 | ~20% | ~20% |
| input_handler/*.py | 249 | ~50% | ~50% |
| **Total** | **~3900** | **~370** | **~9.5%** |

### Was ich anders bauen würde

Tests von Anfang an mitschreiben — insbesondere:

1. **Payment-Handler-Tests** — Für jeden Typ: generate_transactions() mit und ohne Overrides
2. **XML-Builder-Tests** — Generiertes XML gegen XSD validieren (Integration)
3. **Pipeline-Integrationstests** — Excel rein → XML + Report raus
4. **Violation-Tests** — Jede violatable Rule testen: Violation anwenden → Rule muss fehlschlagen

---

## 9. Naming — Konventionen festlegen

### Problem

Gemischte Sprachen und Stile:

- `titel` (Deutsch) neben `remarks` (Englisch)
- `Zahlungstyp` (Excel/Deutsch) vs. `payment_type` (Code/Englisch)
- XML-Terme (`Cdtr`, `RmtInf`) in Python-Variablennamen

### Was ich festlegen würde

| Kontext | Sprache | Beispiel |
|---------|---------|---------|
| Python-Code (Variablen, Funktionen) | Englisch snake_case | `creditor_name`, `payment_type` |
| Pydantic-Felder (Domain) | Englisch snake_case | `debtor.iban`, `amount` |
| Excel-Spalten (User-facing) | Deutsch | `Zahlungstyp`, `Debtor IBAN` |
| Fehlermeldungen (User-facing) | Deutsch | `"Waehrung muss EUR sein"` |
| ISO 20022 / XML | PascalCase (nur in Builders) | `CdtTrfTxInf`, `PmtInf` |
| Business Rule IDs | UPPER-KEBAB | `BR-SEPA-001` |

---

## Empfohlene Reihenfolge

| Phase | Was | Risiko | Aufwand |
|-------|-----|--------|---------|
| **0** | Tests schreiben (ohne Code zu ändern) | Keins | Mittel |
| **1** | TransactionBuilder (Handler-Deduplizierung) | Niedrig | Klein |
| **2** | TestCase-Modell aufräumen | Niedrig | Klein |
| **3** | Pipeline-Klasse aus main.py extrahieren | Mittel | Mittel |
| **4** | Rule Registry (Business Rules zusammenführen) | Mittel | Mittel |
| **5** | Strategy Pattern für Standards | Niedrig | Klein |
| **6** | Override-Handling zentralisieren | Niedrig | Klein |
| **7** | Excel-Parser robuster machen | Niedrig | Klein |

Phase 0 zuerst — ohne Tests ist jedes Refactoring riskant.
