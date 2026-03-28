# SDD: Dual-Standard-Unterstuetzung (SPS 2025 + CBPR+ SR2026)

**Version:** 1.0
**Datum:** 28. Maerz 2026
**Status:** Entwurf
**Basis:** Bestehende Codebase (SPS-only), CBPR+ SR2026 XSD + Rules (SWIFT MyStandards)

---

## 1. Ausgangslage und Motivation

Das System generiert aktuell pain.001.001.09-Zahlungsdateien ausschliesslich gegen das SPS-Schema (`pain.001.001.09.ch.03.xsd`). Bei Validierung gegen das SWIFT MyStandards-Portal treten Fehler auf, weil CBPR+ eigene Strukturanforderungen hat:

- Fehlender Business Application Header (BAH)
- Abweichende Pflichtfelder (UETR mandatory, kein CtrlSum/NbOfTxs auf B-Level)
- Eingeschraenkter Zeichensatz (FIN-X statt SPS Latin-1)
- Strikte Formatvorgaben (DateTime mit UTC-Offset)
- Eigene Business Rules (35 Rules, davon 19 formal)

**Ziel:** Der Benutzer soll pro Testfall waehlen koennen, ob das XML gegen SPS 2025 oder CBPR+ SR2026 generiert und validiert wird.

---

## 2. Business Requirements

### BR-DS-01: Standard-Auswahl pro Testfall
Der Benutzer kann im Excel pro Testfall einen Standard angeben. Gueltige Werte: `sps2025` (Default) und `cbpr+2026`. Ohne Angabe gilt `sps2025`.

### BR-DS-02: Standard-spezifische XSD-Validierung
Jedes generierte XML wird gegen das zum Standard passende XSD validiert:
- `sps2025` → `pain.001.001.09.ch.03.xsd` (im Repo)
- `cbpr+2026` → CBPR+ Usage Guideline XSD (lokal, nicht im Repo)

### BR-DS-03: Standard-spezifische XML-Struktur
Die XML-Generierung muss standardabhaengig unterschiedliche Strukturen erzeugen:

| Element | SPS 2025 | CBPR+ SR2026 |
|---------|----------|-------------|
| GrpHdr/NbOfTxs | Summe aller Tx | Immer "1" |
| GrpHdr/CtrlSum | Summe aller Betraege | **Entfaellt** |
| PmtInf/NbOfTxs | Anzahl Tx im Block | **Entfaellt** |
| PmtInf/CtrlSum | Summe im Block | **Entfaellt** |
| PmtInf/PmtInfId | Generiert (eindeutig) | **= MsgId** (Rule R8) |
| PmtId/UETR | Optional | **Pflicht** (UUIDv4) |
| CreDtTm | ISO 8601 | **Pflicht UTC-Offset** (z.B. `+01:00`) |
| MsgId / EndToEndId | SPS Latin-1 Subset | **FIN-X Zeichensatz** |
| ChrgBr | DEBT/CRED/SHAR/SLEV | DEBT/CRED/SHAR (**kein SLEV**) |
| PmtMtd | TRF | CHK oder TRF |
| BatchBooking | Optional | **Entfaellt** |

### BR-DS-04: Standard-spezifische Business Rules
Jede Business Rule traegt ein Flag welche Standards sie betrifft (`sps`, `cbpr+`, oder `both`). Bei der Validierung werden nur die zum gewaehlten Standard passenden Rules ausgefuehrt.

### BR-DS-05: CBPR+ Einzel-Transaktion
CBPR+ erlaubt maximal 1 PmtInf mit maximal 1 CdtTrfTxInf pro Message. Multi-Payment (GroupId) und TxCount > 1 sind bei `cbpr+2026` nicht zulaessig.

### BR-DS-06: Proprietaere Dateien schuetzen
Das CBPR+ XSD und zugehoerige Dateien von SWIFT MyStandards sind proprietaer und duerfen nicht ins Git-Repository gepusht werden. Sie liegen unter `docs/specs/cbpr+nonpublic/` und werden per `.gitignore` ausgeschlossen.

### BR-DS-07: Graceful Degradation
Wenn `cbpr+2026` als Standard gewaehlt wird aber das CBPR+ XSD nicht vorhanden ist, soll eine klare Fehlermeldung erscheinen mit dem Hinweis, wo das XSD zu beschaffen ist (SWIFT MyStandards).

---

## 3. Datenmodell-Aenderungen

### 3.1 Neues Enum: Standard

```python
class Standard(str, Enum):
    SPS_2025 = "sps2025"
    CBPR_PLUS_2026 = "cbpr+2026"
```

### 3.2 TestCase erweitern

```python
class TestCase(BaseModel):
    ...
    standard: Standard = Standard.SPS_2025  # NEU
```

### 3.3 BusinessRule erweitern

```python
@dataclass(frozen=True)
class BusinessRule:
    rule_id: str
    category: str
    description: str
    applies_to: Optional[Tuple[PaymentType, ...]]
    spec_reference: str
    violatable: bool = False
    standards: Optional[Tuple[Standard, ...]] = None  # NEU: None = alle Standards
```

---

## 4. Betroffene Module

### 4.1 Excel-Parser (`src/input_handler/excel_parser.py`)

**Aenderung:** Neue optionale Spalte "Standard" lesen.

- Gueltige Werte: `sps2025`, `cbpr+2026` (case-insensitive)
- Default: `sps2025`
- Wird auf `TestCase.standard` gemappt

### 4.2 Config (`config.yaml`)

**Aenderung:** Neuer optionaler Eintrag fuer CBPR+ XSD-Pfad.

```yaml
output_path: "./output"
xsd_path: "schemas/pain.001.001.09.ch.03.xsd"
cbpr_xsd_path: "docs/specs/cbpr+nonpublic/CBPRPlus_SR2026_(...).xsd"  # optional
seed: null
report_format: "docx"
```

### 4.3 XSD-Validator (`src/validation/xsd_validator.py`)

**Aenderung:** Dual-Schema Unterstuetzung.

```python
class XsdValidator:
    def __init__(self, sps_xsd_path: str, cbpr_xsd_path: Optional[str] = None):
        self.sps_schema = self._load(sps_xsd_path)
        self.cbpr_schema = self._load(cbpr_xsd_path) if cbpr_xsd_path else None

    def validate(self, xml_doc, standard: Standard) -> Tuple[bool, List[str]]:
        schema = self.cbpr_schema if standard == Standard.CBPR_PLUS_2026 else self.sps_schema
        if schema is None:
            raise RuntimeError("CBPR+ XSD nicht konfiguriert. Bitte cbpr_xsd_path in config.yaml setzen.")
        ...
```

### 4.4 XML-Builder (`src/xml_generator/pain001_builder.py`)

**Aenderung:** Standard-abhaengige Generierung.

Neuer Parameter `standard` fuer `build_pain001_xml()` und `_build_pmt_inf()`:

```python
def build_pain001_xml(instruction: PaymentInstruction, standard: Standard = Standard.SPS_2025):
    ...
```

**CBPR+-spezifisch:**
- `GrpHdr/CtrlSum`: Nicht erzeugen
- `PmtInf/NbOfTxs`: Nicht erzeugen
- `PmtInf/CtrlSum`: Nicht erzeugen
- `PmtInf/PmtInfId`: Auf MsgId setzen
- `GrpHdr/NbOfTxs`: Immer "1"
- `GrpHdr/CreDtTm`: UTC-Offset Format

### 4.5 Business Rules (`src/validation/business_rules.py`)

**Aenderung:** Rules nach Standard filtern.

```python
def validate_all_business_rules(instruction, testcase) -> List[ValidationResult]:
    standard = testcase.standard
    # Nur Rules ausfuehren die zum Standard passen
    ...
```

### 4.6 Rule-Katalog (`src/validation/rule_catalog.py`)

**Aenderung:** `standards`-Feld zu allen bestehenden Rules hinzufuegen + neue CBPR+-Rules.

**Bestehende Rules klassifizieren:**

| Kategorie | Standards |
|-----------|----------|
| BR-HDR-* | SPS only (CBPR+ hat andere Struktur) |
| BR-GEN-* | Beide (Betrag, Zeichensatz, etc.) |
| BR-ADDR-* | Beide |
| BR-SEPA-* | SPS only |
| BR-QR-* | SPS only |
| BR-IBAN-* | SPS only |
| BR-CBPR-001..006 | Beide (bestehende CBPR+ Rules) |

**Neue CBPR+-spezifische Rules (aus SWIFT MyStandards Rules Sheet):**

| Rule-ID | Beschreibung | SWIFT Rule |
|---------|-------------|------------|
| BR-CBPR-R01 | BAH.BusinessMsgId muss GrpHdr.MsgId entsprechen | R1 |
| BR-CBPR-R08 | PmtInfId muss MsgId entsprechen | R8 |
| BR-CBPR-R10 | Wenn PostalAddress vorhanden, Name Pflicht (alle Parteien) | R10/R13/R18/R22/R28/R30/R32-R35 |
| BR-CBPR-R12 | Structured/Unstructured Remittance gegenseitig exklusiv | R12 |
| BR-CBPR-R15 | Agent: Name und PostalAddress muessen paarweise vorhanden sein | R15/R24-R27 |
| BR-CBPR-R20 | InstrForCdtrAgt Codes: jeder Code maximal einmal | R20 |
| BR-CBPR-R06 | InstrForCdtrAgt: HOLD nicht zusammen mit CHQB | R6 |
| BR-CBPR-R07 | InstrForCdtrAgt: TELB nicht zusammen mit PHOB | R7 |
| BR-CBPR-FX1 | FIN-X Zeichensatz fuer MsgId, EndToEndId, PmtInfId | XSD-Type |
| BR-CBPR-DT1 | CreDtTm muss UTC-Offset enthalten | XSD-Type |
| BR-CBPR-TX1 | Maximal 1 Transaktion pro Message | XSD maxOccurs |

### 4.7 Main (`src/main.py`)

**Aenderungen:**
- Standard aus TestCase an Builder und Validator durchreichen
- Bei `cbpr+2026`: Kein Multi-Payment erlaubt (GroupId ignorieren, Warnung ausgeben)
- CBPR+ XSD-Pfad aus Config laden

### 4.8 Payment-Type Handler (`src/payment_types/cbpr_plus.py`)

**Aenderung:** UETR-Generierung ist bereits implementiert. Keine Aenderung noetig.

---

## 5. .gitignore

Neuer Eintrag:

```
# Proprietaere SWIFT CBPR+ Spezifikationen (nicht oeffentlich)
docs/specs/cbpr+nonpublic/
```

---

## 6. Excel-Format

Neue optionale Spalte **"Standard"** (nach "Bemerkungen" oder an beliebiger Position):

| Wert | Bedeutung |
|------|-----------|
| (leer) | Default: `sps2025` |
| `sps2025` | Swiss Payment Standards 2025 |
| `cbpr+2026` | SWIFT CBPR+ SR2026 |

---

## 7. Implementierungsreihenfolge

| Schritt | Beschreibung | Abhaengigkeiten |
|---------|-------------|----------------|
| 1 | `.gitignore` + Extraction-Script fuer CBPR+ Rules | Keine |
| 2 | `Standard` Enum + `TestCase.standard` + Excel-Parser | Keine |
| 3 | `BusinessRule.standards` Feld + bestehende Rules klassifizieren | Schritt 2 |
| 4 | Neue CBPR+ Rules im Katalog registrieren | Schritt 3 |
| 5 | `XsdValidator` Dual-Schema | Schritt 2 |
| 6 | XML-Builder standard-abhaengig | Schritt 2 |
| 7 | `business_rules.py` Standard-Filter | Schritt 3 |
| 8 | `main.py` Integration | Schritte 5-7 |
| 9 | CBPR+ Testfaelle im Excel | Schritt 8 |
| 10 | End-to-End-Test gegen MyStandards | Schritt 9 |

---

## 8. Risiken und Abgrenzungen

### 8.1 BAH (Business Application Header)

Der MyStandards-Validator erwartet einen BAH (`head.001.001.02`), der das pain.001 umschliesst. Das CBPR+ XSD selbst enthaelt keinen BAH. Optionen:

- **Option A (empfohlen):** BAH als separates Wrapper-XML generieren. Eigenes head.001.001.02 XSD beschaffen.
- **Option B:** BAH-Generierung auf spaeter verschieben. Dokumentieren dass der MyStandards-Validator den BAH-Wrapper braucht.

**Entscheidung:** Phase 1 fokussiert auf den pain.001-Inhalt (ohne BAH). BAH wird als separates Feature in Phase 2 implementiert.

### 8.2 Abwaertskompatibilitaet

Bestehende Testfaelle ohne "Standard"-Spalte im Excel funktionieren unveraendert (Default = sps2025). Kein Breaking Change.

### 8.3 CBPR+ XSD-Verfuegbarkeit

Das CBPR+ XSD ist proprietaer (SWIFT MyStandards, kostenloser Login). Fehlt das XSD, wird eine klare Fehlermeldung ausgegeben. Die Validierung faellt auf SPS zurueck wenn gewuenscht.

### 8.4 Namespace-Identitaet

Beide XSDs verwenden denselben Namespace (`urn:iso:std:iso:20022:tech:xsd:pain.001.001.09`). Das bedeutet: ein XML das gegen CBPR+ XSD valide ist, ist **nicht** notwendigerweise gegen SPS XSD valide (und umgekehrt). Die XSD-Auswahl muss korrekt zum Standard passen.

---

## 9. Nicht in Scope

- BAH-Generierung (head.001.001.02)
- pacs.008 Mapping (Interbank-Message)
- CBPR+ Address Grace Period Logic (Structured/Hybrid/Unstructured Uebergangsregeln)
- SWIFT Network Validation (BIC-Verzeichnis-Pruefung)
- Multi-PmtInf fuer CBPR+ (per Spec nicht erlaubt)
