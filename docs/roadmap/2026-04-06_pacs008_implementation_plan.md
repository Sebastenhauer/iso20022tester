# pacs.008 V1 Implementation Plan

**Erstellt:** 2026-04-06
**Status:** Ready to Execute
**Abnahme-Prinzip:** Nach jedem grösseren Work Package (WP) → `pytest` grün + Sanity-Run + FINaplo-Validation der relevanten Outputs.

---

## Scope V1

- **Message:** `pacs.008.001.08` (CBPR+, SR2026)
- **Flavor-Feld vorbereitet** für spätere `TARGET2`, `SIC`, `SEPA` (nicht implementiert, aber Code-Struktur hält es offen)
- **COVE / pacs.009:** out of scope
- **CGI-MP für pacs.008:** out of scope
- **Parse-Inflow-Mode** (existierende XMLs einlesen): out of scope
- **Chain-Derivation pain.001 → pacs.008:** out of scope (siehe `2026-04-06_pain001_pacs008_chain_analysis.md`)
- **Correspondent-Lookup-Map:** out of scope (siehe `2026-04-06_correspondent_lookup_map.md`)

## High-Level Architektur

- **Repo:** gleiches Repo, leichte Asymmetrie (pain.001 bleibt wo es ist, pacs.008 kommt parallel)
- **Entry-Point:** Unified `python -m src.main --input <excel>` mit Header-basierter Auto-Detection + optionalem `--message pain.001|pacs.008` Override
- **Datenmodell:** eigene Modell-Familie `Pacs008TestCase`, `Pacs008Instruction`, `Pacs008Transaction` (keine Wiederverwendung von `TestCase`/`PaymentInstruction`)
- **Feld `pacs008_flavor`:** initial `CBPR+`, vorbereitet für spätere Werte
- **Package-Struktur:** Subpackages parallel zu pain.001
  ```
  src/
    models/
      pacs008.py                   # neu
    xml_generator/
      pacs008/                     # neu (Subpackage)
        __init__.py
        namespaces.py
        builders.py
        message_builder.py         # assemblies Document + AppHdr
    payment_types/pacs008/
      __init__.py
      defaults.py                  # InstgAgt BIC, SttlmMtd, IntrBkSttlmDt etc.
    validation/
      rule_catalog.py              # bestehend, neue BR-CBPR-PACS-* Konstanten
      business_rules.py            # bestehend, neuer Branch
      pacs008_violations.py        # neu, paralleles Registry
    input_handler/
      excel_parser.py              # bestehend, Auto-Detection + pacs.008-Branch
    pipeline.py                    # bestehend, Dispatch auf Message-Type
    finaplo/                       # neu
      __init__.py
      client.py                    # REST Client mit Bearer Auth, per-flavor endpoint
      validator.py                 # High-Level: XML → FINaplo → ValidationResult
  ```
- **Output-Struktur:**
  ```
  output/<timestamp>/
    pain.001/
      *.xml
      testlauf_ergebnis.{json,xml,docx}
    pacs.008/
      *.xml                        # BAH + Document in einem File (BusinessMessage-Wrapper)
      testlauf_ergebnis.{json,xml,docx}
  ```
- **FINaplo-Endpoint je Flavor (R1):**
  - `CBPR+` → `POST /cbpr/validate`
  - `TARGET2` → `POST /target2/validate` (später)
  - `SEPA` → `POST /sepa/{sepaScheme}/validate` (später)
- **FINaplo-Auto-Repair (R3 = 3b + 4a):** nach Fertigstellung läuft ein Subagent-Loop: pipeline run → FINaplo validate → bei Fehlern die Errors interpretieren → Builder/Rule/Testdaten anpassen → rerun → bis alle 50 Testcases grün sind.

---

## Work Packages

### WP-01: Scaffold & Auto-Detection

**Ziel:** Leere Modul-Struktur, unified CLI mit Header-Auto-Detection, Pipeline-Dispatch auf Stubs.

**Tasks:**
- Anlegen aller neuen leeren Files nach obigem Layout
- `src/input_handler/excel_parser.py`: Funktion `detect_message_type(header) -> Literal["pain.001","pacs.008"]`, basierend auf charakteristischen Spalten (`InstgAgt BIC`, `SttlmMtd`, `IntrBkSttlmDt` → pacs.008; `Zahlungstyp`, `Debtor IBAN` → pain.001)
- `src/main.py`: `--message` CLI-Flag, dispatch `run_pain001()` vs `run_pacs008()` (pacs008 ist initial Stub der "nicht implementiert" meldet)
- Tests: `test_message_type_detection.py` mit 4 Fällen (pain.001 vorhanden, pacs.008 vorhanden, ambig → error, override via Flag)

**Abnahme:**
- `python -m src.main --input templates/testfaelle_comprehensive.xlsx` läuft wie vorher (pain.001 Regression ok)
- `python -m src.main --input templates/testfaelle_pacs008_stub.xlsx` erkennt pacs.008 und meldet "noch nicht implementiert"
- `pytest` → 629+ passed (2 neue Tests)

**Dependencies:** keine
**Geschätzter Aufwand:** S (2–3h)

---

### WP-02: Datenmodell

**Ziel:** Pydantic-Modelle für pacs.008 TestCase, Instruction, Transaction, Parties.

**Tasks:**
- `src/models/pacs008.py`:
  - `Pacs008Flavor` Enum (initial: `CBPR_PLUS`)
  - `AgentInfo` (bic: Optional[str], name: Optional[str], address: dict, clearing_system: Optional[str], clearing_member_id: Optional[str])
  - `PartyInfo` (name, address dict, lei: Optional[str])
  - `AccountInfo` (iban: Optional[str], other_id: Optional[str], currency: Optional[str])
  - `ChargesInfo` (amount: Decimal, currency: str, agent: AgentInfo)
  - `Pacs008Transaction` (end_to_end_id, instruction_id, uetr, amount, currency, dbtr, dbtr_acct, cdtr, cdtr_acct, charges: List[ChargesInfo], charge_bearer, intermediary_agents: List[AgentInfo], ultimate_debtor, ultimate_creditor, remittance_info, purpose_code, category_purpose, regulatory_reporting, overrides)
  - `Pacs008Instruction` (msg_id, cre_dt_tm, number_of_tx, ctrl_sum, sttlm_inf, instg_agt, instd_agt, dbtr_agt, cdtr_agt, intr_bk_sttlm_dt, transactions)
  - `Pacs008TestCase` (testcase_id, titel, ziel, expected_result, flavor, violate_rule, overrides, instructions, bah_from_bic, bah_to_bic, expected_api_response, remarks)
- Unit tests: Model-Roundtrip + Validation (pytest + pydantic)

**Abnahme:**
- Alle Felder definiert, Pydantic-Validierung funktioniert
- 5 neue Modell-Tests grün

**Dependencies:** WP-01
**Aufwand:** M (3–4h)

---

### WP-03: Excel-Parser für pacs.008

**Ziel:** Neuer Parser-Branch mit 25+ Spalten, Dot-Notation-Overrides.

**Tasks:**
- Spalten-Set definieren (siehe Liste unten)
- `src/input_handler/excel_parser.py`: Funktion `parse_pacs008_excel(path) -> Tuple[List[Pacs008TestCase], List[str]]`
- Dot-Notation Overrides: `IntrmyAgt1.FinInstnId.BICFI`, `SttlmInf.SttlmAcct.Id.Othr.Id`, `ChrgsInf[0].Amt`, `ChrgsInf[0].Agt.FinInstnId.BICFI` etc.
- `templates/testfaelle_pacs008_minimal.xlsx` anlegen (3 Zeilen, Smoke-Test)
- Unit tests: parser akzeptiert alle 3 Rows, Overrides werden korrekt geparsed

**Spalten-Set (Vorschlag für finalen Review):**
```
TestcaseID, Titel, Ziel, Erwartetes Ergebnis, Flavor,
BAH From BIC, BAH To BIC,
InstgAgt BIC, InstdAgt BIC,
Debtor Name, Debtor Strasse, Debtor Hausnummer, Debtor PLZ, Debtor Ort, Debtor Land,
Debtor IBAN, Debtor Kontonummer, Debtor Kontoschema,
DbtrAgt BIC, DbtrAgt ClrSysMmbId,
IntrmyAgt1 BIC, IntrmyAgt1 ClrSysMmbId, IntrmyAgt2 BIC, IntrmyAgt3 BIC,
Creditor Name, Creditor Strasse, Creditor Hausnummer, Creditor PLZ, Creditor Ort, Creditor Land,
Creditor IBAN, Creditor Kontonummer, Creditor Kontoschema,
CdtrAgt BIC, CdtrAgt ClrSysMmbId,
IntrBkSttlmAmt, Währung, IntrBkSttlmDt, SttlmMtd,
ChrgBr,
UETR,
PurposeCode, CategoryPurpose, Verwendungszweck,
ViolateRule, Weitere Testdaten,
Erwartete API-Antwort, Bemerkungen
```

**Abnahme:**
- `parse_pacs008_excel()` liest 3 Testzeilen fehlerfrei
- Overrides werden in `overrides` dict abgebildet
- 6 neue Tests grün

**Dependencies:** WP-02
**Aufwand:** M (4–5h)

---

### WP-04: Default-Werte-Module

**Ziel:** Zentralisierte Defaults für alle Felder, die der User nicht explizit setzen muss.

**Tasks:**
- `src/payment_types/pacs008/defaults.py`:
  - `DEFAULT_SETTLEMENT_METHOD = "INDA"`
  - `DEFAULT_SETTLEMENT_DATE_OFFSET_DAYS = 1` (T+1)
  - `DEFAULT_CHARGE_BEARER = "SHAR"` (überschreibbar per Excel)
  - `DEFAULT_INSTG_AGT_BIC: Optional[str] = None` (muss User oder BAH From BIC liefern)
  - `DEFAULT_INSTD_AGT_BIC: Optional[str] = None`
  - **Charges: KEIN Default** (User-Antwort #8: keine Default-ChrgsInf wenn nichts kommt)
  - `DEFAULT_INTERMEDIARY_COUNT = 1` (genau einen IntrmyAgt1 setzen falls Flavor=CBPR+ und User nichts angibt)
  - Helper: `resolve_settlement_date(base: date, offset: int, currency: str) -> date` (Banktag-aware)

**Abnahme:**
- Unit tests für `resolve_settlement_date` (Wochenende, Feiertag, Currency-abhängig)
- `defaults.py` wird von allen anderen Modulen als Single Source genutzt

**Dependencies:** WP-02
**Aufwand:** S (2h)

---

### WP-05: XML Builders für pacs.008

**Ziel:** Elemente bauen gemäss `pacs.008.001.08` XSD.

**Tasks:**
- `src/xml_generator/pacs008/namespaces.py`: `PACS008_NS = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"`, `HEAD_NS = ...`
- `src/xml_generator/pacs008/builders.py`:
  - `build_group_header(parent, instruction)` → MsgId, CreDtTm, NbOfTxs, CtrlSum, SttlmInf, InstgAgt, InstdAgt
  - `build_settlement_info(parent, sttlm_mtd, sttlm_acct=None)` → SttlmMtd (Pflicht) + optional SttlmAcct
  - `build_agent(parent, tag_name, agent: AgentInfo)` → BICFI ODER ClrSysMmbId (oder beides)
  - `build_party(parent, tag_name, party: PartyInfo)` → Nm + PstlAdr + optional Id/OrgId/Othr (LEI wrap wie pain.001)
  - `build_charges_info(parent, charges: List[ChargesInfo])` → N × `<ChrgsInf><Amt Ccy=.../><Agt>...</Agt></ChrgsInf>`
  - `build_cdt_trf_tx_inf(parent, tx)` → kompletter C-Level Block mit allen Parties, Agenten, RmtInf, RgltryRptg, Purp, Charges
- `src/xml_generator/pacs008/message_builder.py`:
  - `build_pacs008_document(instruction) -> etree.Element` (nur `<Document>` ohne BAH)
  - `wrap_with_bah(doc, bah_from_bic, bah_to_bic, msg_id) -> etree.Element` (nutzt existierenden `src/xml_generator/bah_builder.py`, erweitert für pacs.008 — `MsgDefIdr=pacs.008.001.08`, `BizSvc=swift.cbprplus.02`)
  - `serialize(root) -> bytes` (pretty-print, UTF-8)

**Abnahme:**
- Kann eine minimale pacs.008 aus einem hardcoded `Pacs008Instruction` erzeugen
- Ausgabe ist XSD-valide gegen `schemas/pacs.008/CBPRPlus_..._pacs_008_001_08_...xsd`
- 10+ Builder-Unit-Tests

**Dependencies:** WP-02, WP-04
**Aufwand:** L (1 Tag)

---

### WP-06: Business Rules Katalog für pacs.008

**Ziel:** Initial ~15 Business Rules aus CBPR+ Usage Guidelines.

**Tasks:**
- `src/validation/rule_catalog.py`: neue Rule-Familie `BR-CBPR-PACS-*`
  - `BR-CBPR-PACS-001` UETR Pflicht
  - `BR-CBPR-PACS-002` InstgAgt BIC Pflicht
  - `BR-CBPR-PACS-003` InstdAgt BIC Pflicht
  - `BR-CBPR-PACS-004` SttlmMtd muss gültig sein (`INDA`, `INGA`, `CLRG`; `COVE` ist out of scope und wird gemeldet)
  - `BR-CBPR-PACS-005` Creditor-Adresse strukturiert
  - `BR-CBPR-PACS-006` Debtor-Adresse strukturiert
  - `BR-CBPR-PACS-007` BAH MsgDefIdr muss `pacs.008.001.08` sein
  - `BR-CBPR-PACS-008` BAH BizSvc muss `swift.cbprplus.02` sein
  - `BR-CBPR-PACS-009` IntrBkSttlmDt muss Banktag sein
  - `BR-CBPR-PACS-010` ChrgBr gültig (`DEBT`, `CRED`, `SHAR`)
  - `BR-CBPR-PACS-011` Währung muss ISO 4217
  - `BR-CBPR-PACS-012` Wenn ChrgsInf vorhanden, Agt Pflicht
  - `BR-CBPR-PACS-013` NbOfTxs muss der Anzahl CdtTrfTxInf entsprechen
  - `BR-CBPR-PACS-014` CtrlSum muss Summe der IntrBkSttlmAmt sein
  - `BR-CBPR-PACS-015` UETR Format (UUIDv4)
- `src/validation/business_rules.py`: neuer Block `validate_pacs008_rules(instruction, testcase) -> List[ValidationResult]`
- Positive + negative Unit Tests je Rule

**Abnahme:**
- Alle 15 Rules im Catalog registriert und exportiert
- 30+ neue Unit Tests (positiv + negativ je Rule)

**Dependencies:** WP-02
**Aufwand:** M (5h)

---

### WP-07: Violations Registry

**Ziel:** Paralleles Pattern zu pain.001 für negative Testing.

**Tasks:**
- `src/validation/pacs008_violations.py`:
  - `PACS008_VIOLATIONS_REGISTRY: Dict[RuleId, Callable]`
  - Mindestens 10 Violation-Funktionen die zu den 15 Rules aus WP-06 passen (manche Rules sind XSD-geschützt, nicht alle violatable)
- `_VIOLATION_FIELD_MAP_PACS008` für Conflict-Detection bei Chaining

**Abnahme:**
- Unit Tests: pro Violation ein Round-Trip-Test (mutate → build → validate → assert rule fails)
- ~15 Tests

**Dependencies:** WP-05, WP-06
**Aufwand:** M (4h)

---

### WP-08: Pipeline Dispatch

**Ziel:** `src/pipeline.py` erweitert, dispatched auf Message-Type.

**Tasks:**
- `PaymentTestPipeline.process()` bekommt neue Methode `process_pacs008(testcases, output_dir)`
- Pacs008 Pipeline erstellt per Testcase:
  1. Instruction aus TestCase bauen (defaults + overrides anwenden)
  2. Violations anwenden (wenn violate_rule gesetzt)
  3. Document bauen → BAH wrappen → in `BusinessMessage`-Container einbetten
  4. XSD-validieren (schemas/pacs.008/...)
  5. Business Rules (BR-CBPR-PACS-*) laufen
  6. File speichern in `output/<timestamp>/pacs.008/`
  7. Reporter aufrufen
- Reporter-Adapter: `src/reporting/` bekommt ein Mapping für pacs.008-Felder (falls nötig); im Zweifel eigene Funktionen

**Abnahme:**
- End-to-end-Run eines Dummy-pacs.008-Excels mit 3 Zeilen erzeugt 3 XMLs + Reports
- Kein Regression auf pain.001 Run

**Dependencies:** WP-03, WP-05, WP-06, WP-07
**Aufwand:** L (1 Tag)

---

### WP-09: FINaplo API Client

**Ziel:** Thin REST Client mit Bearer Auth, Per-Flavor-Endpoint-Dispatch, Retry-Logik.

**Tasks:**
- `src/finaplo/__init__.py`
- `src/finaplo/client.py`:
  - Liest API-Key aus `finaplo/api-key-<date>.txt` (konfigurierbar via env var `FINAPLO_KEY_PATH`)
  - Liest Base-URL aus `finaplo/base-url-<date>.txt`
  - `FinaploClient.validate(xml: bytes, flavor: str) -> FinaploResult`:
    - Flavor → Endpoint-Mapping: `CBPR+` → `/cbpr/validate`, zukünftig `TARGET2` → `/target2/validate`, `SEPA` → `/sepa/{scheme}/validate` (R1)
    - POST mit `Content-Type: text/plain`, `Authorization: Bearer <key>`
    - Response parsing: 200 → valid, 400 → parse errors, 401 → auth error, 500 → server error
  - Exceptions: `FinaploAuthError`, `FinaploValidationError`, `FinaploServerError`
- `src/finaplo/validator.py`:
  - `validate_xml_file(path: Path, flavor: str) -> FinaploResult` als High-Level-Wrapper
- Unit Tests mit `responses` library (HTTP mocks)

**Abnahme:**
- Unit Tests für Auth, Success, Error-Parsing
- Manueller Smoke-Test: gegen Sandbox eine Dummy-XML schicken, Error empfangen, Code erkennt's

**Dependencies:** keine (parallel zu WP-02…08 möglich)
**Aufwand:** M (4h)

---

### WP-10: Test-Daten aus SWIFT Excel extrahieren

**Ziel:** 50 Testcases in `templates/testfaelle_pacs008_comprehensive.xlsx`, davon möglichst viele aus dem offiziellen SWIFT `CBPRPlus_SR2026_..._pacs_008_001_08.xlsx`.

**Tasks:**
- Analyse des SWIFT-Excels: welche Sheets, welche Beispiel-Messages, welche Mappings
- Extraktion-Script: liest das SWIFT-Excel, baut daraus Rohdaten-Rows für unser Format (Field-Mapping)
- Handkuratierte Ergänzung für Fälle die SWIFT nicht abdeckt:
  - Negative Tests (eine Rule je Violation)
  - Unterschiedliche Settlement Methods (INDA, INGA)
  - 2-Hop, 3-Hop Intermediary-Ketten
  - ClrSysMmbId statt BIC (Fedwire, CHAPS)
  - Multi-Tx in einer Message
- Echte BICs: aus öffentlichen Quellen (Wikipedia, Bank-Websites) ziehen — z.B. JPMorgan `CHASUS33XXX`, Deutsche Bank `DEUTDEFFXXX`, UBS `UBSWCHZH80A`, HSBC `HSBCGB2LXXX`, BNP `BNPAFRPPXXX`, Mizuho `MHCBJPJTXXX`, ICBC `ICBKCNBJXXX`, Standard Chartered `SCBLSGSGXXX` usw.
- Coverage aller 15 Items aus Frage #13

**Abnahme:**
- Excel mit 50 Rows parsed fehlerfrei
- Coverage-Checklist aus Frage #13 zu 100% erfüllt (dokumentiert als Kommentar in der Datei oder separates Coverage-Sheet)
- Mindestens 10 negative Testcases mit `ViolateRule`

**Dependencies:** WP-03
**Aufwand:** L (1–1.5 Tage)

---

### WP-11: Full-Run & FINaplo-Integration im Pipeline

**Ziel:** Nach jedem Run werden alle pacs.008 XMLs automatisch via FINaplo validiert und Ergebnisse in den Report aufgenommen.

**Tasks:**
- `src/pipeline.py` (pacs.008 branch): nach XSD + Business Rules ruft die Pipeline optional `FinaploClient.validate()` auf
- CLI-Flag `--finaplo` (default: off, explizit aktivieren)
- Report-Integration: FINaplo-Ergebnis als dritte Validierungs-Spalte neben XSD und Business Rules
- Rate-Limit-Aware (auch wenn kein Limit bekannt, defensive Retry + Backoff)

**Abnahme:**
- `python -m src.main --input testfaelle_pacs008_comprehensive.xlsx --finaplo` läuft durch alle 50 Testcases
- Report zeigt XSD, BR, FINaplo Status pro Testcase
- Bei API-Fehlern wird Testcase als Fail markiert, Run bricht nicht ab

**Dependencies:** WP-08, WP-09
**Aufwand:** M (4h)

---

### WP-12: FINaplo Auto-Repair Loop (R3=3b + R4=4a)

**Ziel:** Subagent-gesteuerter Loop, der nach dem ersten Full-Run fehlschlagende Cases analysiert und iterativ Code/Rules/Testdaten fixt, bis alle 50 grün sind.

**Tasks:**
- Nicht als permanenter Code, sondern als **Ad-hoc Claude-Subagent-Task** im Agent-Mode:
  1. Lese alle FINaplo-Fehler aus dem Report
  2. Gruppe ähnliche Fehler
  3. Pro Gruppe: identifiziere Root Cause (Builder-Bug, falsche Rule, falsche Testdaten)
  4. Patch anwenden
  5. Re-run
  6. Repeat bis grün oder bis 3 Iterationen erfolglos (dann eskalieren)
- Logging aller Iterationen in `output/<timestamp>/finaplo_repair_log.md`

**Abnahme:**
- Am Ende: 50/50 grün gegen FINaplo (Sandbox oder Live)
- Repair-Log dokumentiert alle gefundenen Issues und Fixes

**Dependencies:** WP-11, komplette V1 steht
**Aufwand:** Variabel (1–3 Tage, hängt von Fehleranzahl ab)

---

### WP-13: Dokumentation

**Ziel:** README-Update, CLAUDE.md-Update, neue Docs.

**Tasks:**
- `README.md`: pacs.008 Sektion hinzufügen (Usage, Excel-Format, Flavors)
- `CLAUDE.md`: neue Konventionen für pacs.008 (Flavor-Modell, Charges-Handling, BAH Wrapping, FINaplo-Integration)
- `docs/pacs008_implementation.md`: technisches Deep-Dive, Field-Mapping, Override-Keys
- `docs/finaplo_integration.md`: wie Key konfigurieren, wie API testen

**Abnahme:**
- Alle neuen Docs vorhanden, Code-Beispiele getestet
- CLAUDE.md aktualisiert, neue Konventionen klar dokumentiert

**Dependencies:** WP-12
**Aufwand:** S (2h)

---

## Dependency-Graph

```
WP-01 (Scaffold)
  └─ WP-02 (Datenmodell)
       ├─ WP-03 (Excel-Parser)          ┐
       ├─ WP-04 (Defaults)               │
       ├─ WP-05 (Builders) ← WP-04       │
       ├─ WP-06 (Business Rules)         │
       ├─ WP-07 (Violations) ← WP-05,06  │
       └─ WP-08 (Pipeline) ← WP-03,05,06,07
                                         │
WP-09 (FINaplo Client) ──────────────────┤
                                         │
WP-10 (Test Data) ← WP-03                │
                                         │
WP-11 (FINaplo Pipeline Integration) ← WP-08, WP-09
                                         │
WP-12 (Auto-Repair Loop) ← WP-11, WP-10
                                         │
WP-13 (Dokumentation) ← WP-12
```

**Parallelisierungs-Möglichkeiten:**
- WP-04 + WP-06 + WP-09 können parallel zu WP-03 laufen
- WP-10 (Test-Daten-Extraktion) kann sehr früh starten, sobald WP-03 (Parser) steht
- WP-09 (FINaplo Client) komplett entkoppelt, jederzeit machbar

## Abnahmeprotokoll (nach jedem WP)

Nach jedem abgeschlossenen WP:
1. `pytest` → **alle** Tests grün (nicht nur die neuen)
2. Regression-Smoke-Test pain.001: `python -m src.main --input templates/testfaelle_comprehensive.xlsx --config config.yaml` → 137/137 Pass
3. Falls WP XML-Generierung betrifft: XSD-Validation des Outputs muss grün sein
4. Ab WP-11: zusätzlich FINaplo-Validation der relevanten Outputs muss grün sein
5. Commit mit klarer Message nach Template: `pacs.008: WP-XX <title>` + Body mit Acceptance-Kriterien erfüllt
6. Push nach jedem abgeschlossenen WP (oder nach Gruppe aus 2–3 eng verwandten kleinen WPs)

## Grobe Gesamt-Aufwandsschätzung

| Paket | Aufwand |
|---|---|
| WP-01 Scaffold | S (2–3h) |
| WP-02 Datenmodell | M (3–4h) |
| WP-03 Excel-Parser | M (4–5h) |
| WP-04 Defaults | S (2h) |
| WP-05 Builders | L (1 Tag) |
| WP-06 Business Rules | M (5h) |
| WP-07 Violations | M (4h) |
| WP-08 Pipeline | L (1 Tag) |
| WP-09 FINaplo Client | M (4h) |
| WP-10 Test-Daten | L (1–1.5 Tage) |
| WP-11 FINaplo Pipeline | M (4h) |
| WP-12 Auto-Repair | Variabel (1–3 Tage) |
| WP-13 Dokumentation | S (2h) |
| **Total** | **~8–12 Personen-Tage** |

## Offene Punkte

- **R3 = "a":** unklar welcher Frage das zugeordnet ist; ich frage gleich zurück.
- **FINaplo Sandbox vs Live:** im Swagger stehen beide. Starten wir mit Sandbox (Default) und schalten auf Live um, sobald Credentials funktionieren?
- **`Content-Type: text/plain` vs `application/xml`:** Swagger sagt text/plain. Ich verwende das, falls es nicht geht probieren wir application/xml.
