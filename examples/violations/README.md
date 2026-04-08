# Standards-Differenz-Demo Files

Diese drei XML-Dateien illustrieren konkrete Unterschiede zwischen den Implementation Guides **SPS 2025** und **CGI-MP November 2025**, wie sie im Vergleichsdokument `docs/specs/pain.001/vergleich-sps-cgi-2025.md` analysiert wurden.

Generiert von `scripts/generate_violation_demos.py` auf Basis von Excel-Testfaellen aus `templates/testfaelle_comprehensive.xlsx`.

## Dateien

| Datei | SPS | CGI-MP | Erklaerung |
|---|---|---|---|
| `cgi_mp_argentina_baseline.xml` | ✅ PASS | ✅ PASS | Sauberer Baseline-Run: CGI-MP konformer EUR-Auftrag CH→AR mit vollstaendigem RgltryRptg + TaxRmt |
| `cgi_mp_violates_sps_xsd.xml` | ❌ FAIL | ✅ PASS | Demo: das `★`-Zeichen in `Cdtr/Nm` ist UTF-8-konform (CGI-MP erlaubt) aber verletzt die SPS Latin-1+Extended-A Pattern-Restriction |
| `sps_violates_cgi_unstructured_address.xml` | ✅ PASS | ❌ FAIL | Demo: `UltmtDbtr/PstlAdr` mit nur `AdrLine` (unstrukturiert) ist SPS-konform (Variante "unstrukturiert" laut IG Kapitel 3.11), verletzt aber `BR-CGI-ADDR-02` (CGI: keine unstrukturierten Adressen fuer UltmtDbtr/UltmtCdtr/InitgPty) |

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

## 3. sps_violates_cgi_unstructured_address.xml

Basiert auf der TC-S-001 SPS-Smoke-XML, mit einem `UltmtDbtr`-Element injiziert, dessen `PstlAdr` ausschliesslich `AdrLine`-Subelemente (unstrukturiert) plus die Pflicht-`Ctry` enthaelt:

```diff
       <Amt>
         <InstdAmt Ccy="EUR">1500</InstdAmt>
       </Amt>
+      <UltmtDbtr>
+        <Nm>Mutterkonzern Holding AG</Nm>
+        <PstlAdr>
+          <Ctry>CH</Ctry>
+          <AdrLine>Bahnhofstrasse 100</AdrLine>
+          <AdrLine>8001 Zurich, Switzerland</AdrLine>
+        </PstlAdr>
+      </UltmtDbtr>
       <Cdtr>
         ...
```

**Warum SPS-konform?** SPS IG Kapitel 3.11 ("Verwendung von Adressinformationen") erlaubt drei Adressformate: strukturiert, hybrid, und **unstrukturiert** (nur `AdrLine` plus `Ctry`). Die unstrukturierte Variante ist bis November 2026 explizit zugelassen. SPS hat keine Sonderregel, die das Adress-Format fuer `UltmtDbtr` einschraenkt. Verifizierbar gegen das Schema:

```bash
poetry run python -c "
from lxml import etree
schema = etree.XMLSchema(etree.parse('schemas/pain.001/pain.001.001.09.ch.03.xsd'))
doc = etree.parse('examples/violations/sps_violates_cgi_unstructured_address.xml')
print('SPS-XSD valid:', schema.validate(doc))
"
```
→ `True`

**Warum CGI-MP-violating?** CGI-MP Handbook Slide 8: *"Unstructured: CGI-MP note: Not allowed for Ultimate Debtor, Ultimate Creditor, Initiating Party"*. Im Repo abgebildet als `BR-CGI-ADDR-02` ("Unstructured Adresse verboten fuer UltmtDbtr, UltmtCdtr, InitgPty"). Ein CGI-MP-konformer Validator wuerde dieses XML zurueckweisen, weil das `UltmtDbtr/PstlAdr` kein einziges strukturiertes Adresselement (`StrtNm`, `BldgNb`, `PstCd`, `TwnNm`) enthaelt — nur `AdrLine` + `Ctry`. CGI verlangt fuer diese drei Party-Typen mindestens hybride Form.

**Frühere Iterationen dieses Demo-Files:**
- Erst: leere `<PmtTpInf/>` und `<RmtInf/>` injiziert. Verstoss gegen **SPS CH07** (PmtTpInf B+C exklusiv) und SPS IG **Kapitel 3.4** ("Verwendung leerer Elemente nicht zulaessig").
- Dann: nur `<RmtInf></RmtInf>` in Open-Close-Form. Auch verworfen — SPS Kapitel 3.4 verbietet leere Elemente in jeder Form, egal ob self-closing oder open-close. Es gibt **kein** SPS-vs-CGI-Delta auf der Empty-Tag-Achse, weil beide Standards leere Elemente verbieten.
- Final: unstrukturierte `UltmtDbtr`-Adresse — saubere Demo, weil SPS bis Nov 2026 unstrukturierte Adressen generell zulaesst, CGI sie aber speziell fuer Ultimate Parties verbietet.

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
