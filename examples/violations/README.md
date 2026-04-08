# Standards-Differenz-Demo Files

Diese drei XML-Dateien illustrieren konkrete Unterschiede zwischen den Implementation Guides **SPS 2025** und **CGI-MP November 2025**, wie sie im Vergleichsdokument `docs/specs/pain.001/vergleich-sps-cgi-2025.md` analysiert wurden.

Generiert von `scripts/generate_violation_demos.py` auf Basis von Excel-Testfaellen aus `templates/testfaelle_comprehensive.xlsx`.

## Dateien

| Datei | SPS-XSD | CGI-MP-Best-Practice | Erklaerung |
|---|---|---|---|
| `cgi_mp_argentina_baseline.xml` | ✅ PASS | ✅ PASS | Sauberer Baseline-Run: CGI-MP konformer EUR-Auftrag CH→AR mit vollstaendigem RgltryRptg + TaxRmt |
| `cgi_mp_violates_sps_xsd.xml` | ❌ FAIL | ✅ PASS | Demo: das `★`-Zeichen in `Cdtr/Nm` ist UTF-8-konform (CGI-MP erlaubt) aber verletzt die SPS Latin-1+Extended-A Pattern-Restriction |
| `sps_violates_cgi_empty_tags.xml` | ✅ PASS | ❌ FAIL | Demo: leere `<PmtTpInf/>` und `<RmtInf/>` Tags sind XSD-valide (alle Sub-Elemente optional) aber verletzen `BR-CGI-CHAR-01` ("empty tags must not be used") |

## 1. cgi_mp_argentina_baseline.xml

Ein realer pain.001-Cross-Border-Auftrag mit:

- **Debtor:** Schweizer Tochter AG (CH IBAN, UBS Zurich)
- **Creditor:** Compania Argentina de Comercio S.A., Avenida Corrientes 1234, Buenos Aires, AR
- **Amount:** EUR 85'000.00
- **Charge Bearer:** DEBT
- **Service Level:** URGP, Category Purpose: SUPP
- **Regulatory Reporting:** DbtCdtRptgInd=DEBT, Authrty=SNB/CH, Dtls Tp=BOP/Cd=BOP/Inf="Goods import South America"
- **Tax Remittance:** AdmstnZone=AR, Mtd=VAT, beide TaxIDs (CH+AR), TtlTaxAmt EUR 8'500

Passt durch das SPS-XSD und ist CGI-MP-best-practice-konform.

## 2. cgi_mp_violates_sps_xsd.xml

Identisch zur Baseline, aber `Cdtr/Nm` enthaelt das Unicode-Zeichen `★` (U+2605, BLACK STAR):

```diff
- <Nm>Compania Argentina de Comercio S.A.</Nm>
+ <Nm>Compania Argentina ★ Comercio S.A.</Nm>
```

**Warum CGI-MP-konform?** CGI-MP Handbook (Slide 4) erlaubt explizit den vollen UTF-8-Zeichensatz; jedes XML-konforme Zeichen ist erlaubt. Symbole wie ★ sind kein Verstoss.

**Warum SPS-XSD violating?** Das Schema `pain.001.001.09.ch.03.xsd` enthaelt eine Pattern-Facet auf Text-Feldern:
```
[\p{IsBasicLatin}\p{IsLatin-1Supplement}\p{IsLatinExtended-A}€ȘșȚț-[\p{C}]]+
```
U+2605 liegt in "General Punctuation" (U+2000-U+206F) und damit ausserhalb der drei zugelassenen Latin-Bloecke + den 5 explizit erlaubten Sonderzeichen. Die SPS-XSD-Validation gibt daher:

```
line 64: Element 'Nm': [facet 'pattern'] The value 'Compania Argentina ★ Comercio S.A.'
is not accepted by the pattern '[\p{IsBasicLatin}\p{IsLatin-1Supplement}\p{IsLatinExtended-A}€ȘșȚț-[\p{C}]]+'.
```

**Reproduzieren:**
```bash
poetry run python -c "
from lxml import etree
schema = etree.XMLSchema(etree.parse('schemas/pain.001/pain.001.001.09.ch.03.xsd'))
doc = etree.parse('examples/violations/cgi_mp_violates_sps_xsd.xml')
print('SPS-XSD valid:', schema.validate(doc))
for e in schema.error_log: print(' ', e.message[:200])
"
```

## 3. sps_violates_cgi_empty_tags.xml

Basiert auf der TC-S-001 SPS-Smoke-XML, mit zwei zusaetzlichen Empty Tags injiziert in das `CdtTrfTxInf`-Element:

```diff
       <PmtId>
         ...
       </PmtId>
+      <PmtTpInf/>
       <Amt>
         <InstdAmt Ccy="EUR">1500</InstdAmt>
       </Amt>
       ...
+      <RmtInf/>
     </CdtTrfTxInf>
```

**Warum SPS-XSD-konform?** Beide Element-Typen (`PaymentTypeInformation26` fuer PmtTpInf und `RemittanceInformation16` fuer RmtInf) haben ausschliesslich optionale Sub-Elemente in der XSD-Definition. Ein leerer Container ist daher schema-valide. Verifizierbar via `lxml`:

```bash
poetry run python -c "
from lxml import etree
schema = etree.XMLSchema(etree.parse('schemas/pain.001/pain.001.001.09.ch.03.xsd'))
doc = etree.parse('examples/violations/sps_violates_cgi_empty_tags.xml')
print('SPS-XSD valid:', schema.validate(doc))
"
```
→ `True`

**Warum CGI-MP-violating?** CGI-MP Handbook Slide 4: *"Empty tags (without a value) or tags containing only blanks must not be used per CGI-MP guidelines."* Der Rule-Catalog im Repo registriert das als `BR-CGI-CHAR-01` (`Leere XML-Tags (ohne Wert oder nur Blanks) verboten`).

> **Hinweis:** Im aktuellen Code ist `BR-CGI-CHAR-01` im Rule-Catalog registriert, hat aber **keinen Runtime-Executor** in `src/validation/business_rules.py`. Unser lokaler Pipeline-Validator wuerde diese Datei daher nicht als Fail markieren. Ein externer CGI-MP-konformer Validator (z.B. XMLdation) wuerde sie ablehnen.

## Reproducibility

Beide Demo-Generierungen sind deterministisch und re-runbar:

```bash
# 1. Pipeline-Run, der den Source-Testcase TC-DEMO-CGI-AR und einen frischen TC-S-001 erzeugt
poetry run python -m src.main \
    --input templates/testfaelle_comprehensive.xlsx \
    --config config.yaml

# 2. Mutator: nimmt die zuletzt generierten XMLs und schreibt die 3 Demo-Files
poetry run python scripts/generate_violation_demos.py
```

Das Script greift immer auf den letzten `output/<timestamp>/`-Ordner zu.

## Bezug zum Comparison-Dokument

Diese Files demonstrieren konkret die Punkte 2 (Zeichensatz) und 3 (Empty Tags und Whitespace) aus `docs/specs/pain.001/vergleich-sps-cgi-2025.md`. Andere Differenzen (Address-Rules, RgltryRptg-Pflichtigkeit, OrgId/SchmeNm Cd-only, PmtTpInf/SvcLvl-Pflicht) werden bereits durch die existierenden TC-CGI-* und TC-REG-* Testfaelle in `templates/testfaelle_comprehensive.xlsx` abgedeckt.
