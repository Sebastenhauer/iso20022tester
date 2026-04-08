# Vergleich: SPS 2025 (Typ X) vs. CGI-MP pain.001.001.09

## Quellen

| Standard | Dokument | Version | Zugang |
|----------|----------|---------|--------|
| **SPS 2025** | IG Credit Transfer SPS 2025 | v2.2 (24.02.2025) | SIX Group, lokal: `docs/specs/pain.001/ig-credit-transfer-sps-2025-de.md` |
| **SPS 2025** | Business Rules SPS 2025 | v3.2 | SIX Group, lokal: `docs/specs/pain.001/business-rules-sps-2025-de.md` |
| **CGI-MP** | WG1 User Handbook pain.001.001.09 | November 2025 Update | SWIFT MyStandards (Login erforderlich), lokal: `docs/specs/cgi_nonpublic/CGI-MP_WG1_User_Handbook_pain001_Nov2025.md` |
| **CGI-MP** | Appendix B Local Country Rules | Februar 2025 | SWIFT MyStandards |

## Zusammenfassung

CGI-MP (Common Global Implementation Market Practice) ist der **globale Corporate-to-Bank Standard** und harmonisiert pain.001-Implementierungen weltweit fuer multinationale Unternehmen, die eine einzige Format-Variante an mehrere Banken weltweit senden wollen. SPS 2025 ist die **Schweizer Adaption** desselben ISO-20022-Schemas, die zusaetzliche Domestic-Anforderungen (QR-Bill, SPS-Charset, SIC-spezifische Regeln) abdeckt.

Die zwei Standards sind weitgehend kompatibel auf der Schema-Ebene (beide nutzen `pain.001.001.09`), unterscheiden sich aber in Details bei Charset, Adressrules, Transaktionsstrukturierung, Pflichtfeldern und der Behandlung von Empty Tags.

## Detailvergleich

### 1. Schema und Versionierung

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **XSD** | `pain.001.001.09.ch.03` (CH-Variante) | Standard ISO `pain.001.001.09` |
| **Basis-Version** | ISO 2019 | ISO 2019 |
| **Validation** | XSD + SPS-Business-Rules | XSD + CGI-MP-Best-Practice + Bank-spezifische Regeln |
| **Aktualisierungen** | Februar 2025 (v2.2) | November 2025 Update |
| **Identisch?** | Im Schema gleich, in Restrictions unterschiedlich |

### 2. Zeichensatz

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **Generelle Textfelder** | UTF-8 eingeschraenkt: Basic-Latin (U+0020..U+007E), Latin1-Supplement (U+00A0..U+00FF), Latin Extended-A (U+0100..U+017F), plus `Ș ș Ț ț €` | **UTF-8 voll** (alle Unicode-Zeichen erlaubt) |
| **Reference-Felder** (MsgId, PmtInfId, InstrId, EndToEndId) | SPS Reference Charset: `[A-Za-z0-9 +-/?:().,'#@!$%&*={}\|~"<>;]` (gleicher Subset wie CBPR+ FIN-X) | Empfehlung "limited charset" (nicht erzwungen, bilateral) |
| **Verbindlichkeit** | Bei Verstoss wird Meldung **abgelehnt** | Banken konvertieren bei Bedarf, ERP/TMS-Systeme bieten Konversion an |
| **Identisch?** | **Nein** — SPS ist deutlich strenger |

**Konsequenz:** CGI-MP-konforme Nachrichten mit z.B. CJK-Zeichen oder kyrillischen Namen sind in SPS nicht zulaessig. Eine CGI-MP→SPS-Konversion erfordert Charset-Mapping (z.B. Transliteration).

### 3. Empty Tags und Whitespace

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **Leere Tags ohne Wert** | Erlaubt, werden ignoriert | **Nicht zulaessig** (`empty tags must not be used`) |
| **Tags nur mit Blanks** | Erlaubt | **Nicht zulaessig** |
| **Identisch?** | **Nein** — CGI-MP ist hier strenger |

**Konsequenz:** CGI-MP-Generatoren muessen Empty Tags aktiv unterdruecken; SPS-Generatoren koennen sie tolerieren. Best Practice: in beiden Faellen vermeiden.

### 4. Transaktionen pro Nachricht

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **PmtInf pro Message** | 1..n | 1..n (typischerweise 1) |
| **CdtTrfTxInf pro PmtInf** | 1..n | 1..n |
| **NbOfTxs** | Summe aller Tx | Summe aller Tx |
| **CtrlSum** (GrpHdr) | Vorhanden, Summe aller Betraege | Vorhanden |
| **CtrlSum** (PmtInf) | Vorhanden, Summe im Block | Vorhanden |
| **BatchBooking** | Optional | Optional |
| **Identisch?** | **Ja** (gleiche Struktur, im Gegensatz zu CBPR+ Relay) |

### 5. Pflichtfelder und Identifikation

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **MsgId** | Pflicht | Pflicht. CGI-MP empfiehlt restricted charset; Forwarding Agent ersetzt MsgId beim Relay an CBPR+ |
| **InitgPty** | Pflicht (Name) | Pflicht (Name); strukturierte Adresse empfohlen |
| **PmtInfId** | Pflicht (eindeutig) | Pflicht. Kann gleich oder verschieden zu MsgId sein |
| **InstrId** | Optional (empfohlen) | Optional |
| **EndToEndId** | Pflicht | Pflicht. Empfehlung restricted charset |
| **UETR** | **Optional** (empfohlen) | **Optional**. Bank empfiehlt Corporates die Lieferung; bilateral vereinbart. Bei Relay an CBPR+ vom Forwarding Agent generiert wenn nicht vorhanden |
| **Identisch?** | Sehr aehnlich, beide Optional |

### 6. Adressanforderungen

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **Strukturiert** | Empfohlen, alle Subelemente | Empfohlen, alle Subelemente |
| **Hybrid** | Erlaubt **ab November 2025**: strukturierte Felder + max 2 AdrLines a 70 Zeichen, keine Duplikation | Erlaubt **ab November 2025** (Transition bis November 2026), gleiche Regeln |
| **Unstrukturiert (nur AdrLines)** | Bis November 2026 erlaubt, danach nur noch hybrid/strukturiert | Bis November 2026 erlaubt, danach **eliminiert** |
| **TwnNm + Ctry** | Pflicht in strukturierter und hybrider Variante | Pflicht (Country mandatory; Town Name recommended → mandatory ab Nov 2025 fuer urgent/international) |
| **AdrLine max** | 2 Zeilen (in hybrider Variante) | 7 Zeilen in unstrukturierter Variante; 2 Zeilen im hybriden Modus |
| **UltmtDbtr/UltmtCdtr** | Strukturiert empfohlen | **Unstrukturiert nicht erlaubt** fuer UltmtDbtr/UltmtCdtr/InitgPty (BR-CGI-ADDR-02) |
| **AddressType** | Optional, in pain.001.001.09 (`AdrTp`) | Erlaubt, aber nicht im Best-Practice-Set |
| **Identisch?** | Im Wesentlichen ja, kleine Unterschiede in Restrictions |

### 7. Regulatory Reporting

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **Element vorhanden** | **Ja** — `RgltryRptg` [0..10] auf C-Level | **Ja** — `RgltryRptg` [0..10] auf C-Level |
| **Verwendung** | Optional ("O"). Wird nur im Interbankverkehr **ins Ausland** weitergeleitet. Pflicht fuer bestimmte Zielländer (z.B. Vereinigte Arabische Emirate) | Optional, aber **erforderlich wenn von Regulator verlangt**. Detaillierte Verwendungsregeln in Appendix B (tabs "Regulat. Rpt. Out" und "Regulat. Rpt. In") |
| **Zahlungsart D V2** | Darf nicht geliefert werden (Domestic V2 ohne Foreign Exchange Service) | nicht relevant (CGI-MP ist nicht Domestic) |
| **DbtCdtRptgInd** | Optional (CRED, DEBT, BOTH) — fuer UAE Pflicht | **Pflicht wenn `RgltryRptg` verwendet** (CRED oder DEBT; BOTH derzeit nicht verwendet) |
| **Authrty (Behoerde)** | Optional (Name + Country); wenn verwendet, einmalig | Optional. Wenn verwendet, einmalig pro Indicator |
| **Dtls/Tp** | Optional | **Pflicht wenn `Dtls` verwendet**. Best-Practice-Werte: PURP, CRST, CIST, PUFD |
| **Dtls/Cd** | Optional, max 10 Zeichen. CH21-Regel: nur zulaessig zusammen mit `Dtls/Ctry` | Max 10 Zeichen, vom Regulator oder von der Bank vergeben |
| **Dtls/Inf** | Optional textuell | Optional textuell |
| **Bezug zu Purpose** | Bei UAE darf "Purpose of Payment" nicht im `Purp`-Feld stehen, sondern im RgltryRptg | **Muss** unter RgltryRptg, **nicht** unter Purp gefuehrt werden, wenn regulatorisch verlangt |
| **Identisch?** | **Konzeptionell identisch**, in Pflichtigkeit der Sub-Elemente leicht unterschiedlich (CGI-MP strenger bei DbtCdtRptgInd und Dtls/Tp) |

> **Korrektur einer fruehren Doku-Aussage:** Die README hatte `RgltryRptg` fuer SPS 2025 als "—" markiert. Korrekt ist: SPS unterstuetzt das Element optional (0..10), gemaess SPS IG v2.2 Seite 68. Nur fuer Domestic-Zahlungsart V2 ist es explizit verboten.

### 8. Tax Information

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **TaxRmt** in `RmtInf/Strd` | Optional, selten genutzt | Optional, "rare use case", **bilateral vereinbart** (nicht Best Practice) |
| **`<Tax>`-Komponente** | Vorhanden im Schema, selten verwendet | Verwendet fuer Withholding-Tax-Belege (Thailand, Philippines), gekoppelt mit `CtgyPurp=WHLD` |
| **Tax Identification unter Party** (`Id/OrgId/Othr/SchmeNm/Cd=TXID`) | Erlaubt | Best Practice fuer Tax-ID des Debtors/Creditors |
| **Tax Reference unter `RgltryRptg`** | Implizit ueber `Dtls` | Best Practice fuer UK HMRC RTI |
| **Identisch?** | Ja, beide unterstuetzen alle vier Tax-Bereiche |

### 9. Remittance Information

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **Structured / Unstructured Exclusivity** | Gegenseitig exklusiv | Gegenseitig exklusiv |
| **Unstructured max** | 140 Zeichen, 1 Occurrence | 140 Zeichen, 1 Occurrence |
| **AddtlRmtInf** | Bis 3 Mal | Bis 3 Mal, **Best Practice nur 1** |
| **Structured max** | Markteinschraenkungen pro Zahlungsart | Bis Nov 2025: bilateral. **Ab Nov 2025: max 9000 Zeichen** ohne bilaterales Agreement |
| **CdtrRefInf Codes** | SCOR (mit ISO 11649), QRR (Domestic, als `Prtry`) | SCOR (Best Practice), DISP, FXDR, PUOR, RPIN, RADM |
| **RfrdDocInf Type Codes** | Nicht im Detail eingeschraenkt | CINV, CREN, AROI, BOLD, CMCN, CNFA, DEBN, DNFA, DISP, HIRI, MSIN, PUOR, SBIN, SOAC, TSUT, VCHR (ISO Codes) |
| **Tax/Garnishment Remittance** | Vorhanden im Schema | Vorhanden im Schema, "not part of best practice" |
| **Identisch?** | Schema gleich; CGI-MP hat strengere Best-Practice-Empfehlungen (RfrdDocInf Type, Quantitaet AddtlRmtInf) |

### 10. Purpose und Category Purpose

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **`Purp/Cd`** | Optional. Codes aus ISO ExternalPurpose1Code | Optional. Best Practice: ISO Code statt Proprietary |
| **`PmtTpInf/CtgyPurp/Cd`** | Optional. Codes aus ISO ExternalCategoryPurpose1Code | Optional. Best Practice: ISO Code |
| **Verbot Purpose mit Regulatory Reporting** | Implizit (Regulatory ist separates Element) | **Explizit:** Regulatory Reporting darf nicht in `Purp` stehen, sondern unter `RgltryRptg` |
| **WHLD Trigger** | Nicht explizit erzwungen | `CtgyPurp=WHLD` triggert die `Tax`-Komponente fuer Withholding-Tax-Evidenz |
| **Identisch?** | Ja, mit kleinen Best-Practice-Unterschieden |

### 11. Ultimate Parties

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **UltmtDbtr** | Optional auf B-Level oder C-Level | Optional auf C-Level (Best Practice) |
| **UltmtCdtr** | Optional auf C-Level | Optional auf C-Level |
| **Adresse** | Wenn vorhanden, strukturiert empfohlen | **Unstrukturiert nicht erlaubt** (BR-CGI-ADDR-02). Hybrid erst ab Nov 2025; bis dahin nur strukturiert mit min. TownName + Country |
| **InitgPty** (Adresse) | Strukturiert empfohlen | **Unstrukturiert nicht erlaubt** |
| **Identisch?** | Ja, mit strengerer CGI-MP-Best-Practice fuer InitgPty/Ultimate-Parties |

### 12. Payment Method (PmtMtd)

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **TRF** | Erlaubt (Default) | Erlaubt (Best Practice fuer Non-Cheque) |
| **CHK** | Vorhanden im Schema, aber nicht verwendet ("Phase 1 nur TRF") | Erlaubt fuer Cheque-Zahlungen |
| **TRA** | Im Schema vorhanden | Erlaubt |
| **Identisch?** | Schema gleich; SPS in der Praxis nur TRF |

### 13. Charge Bearer (ChrgBr)

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **DEBT, CRED, SHAR** | Alle erlaubt | Alle erlaubt |
| **SLEV** | Erlaubt (SEPA Pflicht) | Erlaubt (SEPA Pflicht) |
| **Position** | B-Level oder C-Level | B-Level oder C-Level |
| **Default-Werte** | Keine; pro Zahlungsart unterschiedlich | Keine |
| **Identisch?** | Ja |

### 14. PmtTpInf / Service Level

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **`SvcLvl/Cd=SEPA`** | Pflicht fuer SEPA (Zahlungsart S) | **Pflicht fuer SEPA** (strenger als EPC; CGI-MP enforced "must be present") |
| **PmtTpInf Position** | B-Level oder C-Level (nicht beides) | **PmtTpInf muss auf B- oder C-Level stehen** (nicht beides simultan) — `SvcLvl` ist Pflicht innerhalb |
| **Identisch?** | Konzeptionell ja; CGI-MP ist hier durch eigene Validation strenger |

### 15. OrgId und SchmeNm

| Aspekt | SPS 2025 | CGI-MP |
|--------|----------|--------|
| **`OrgId/Othr/SchmeNm`** | Beide `Cd` und `Prtry` erlaubt; CH21 verlangt `AnyBIC` oder `Othr` (kein bare LEI) | **Nur `Cd` erlaubt**, `Prtry` nicht zulaessig. Wert aus `ExternalOrganisationIdentification1Code` |
| **LEI** | Kann als `Othr/Id` mit `SchmeNm/Cd=LEI` abgebildet werden, oder als `<LEI>`-Element direkt | **Empfehlung: `<LEI>`-Element direkt** (V09-Erweiterung), bzw. `Othr/SchmeNm/Cd` |
| **Identisch?** | Konzeptionell aehnlich, CGI-MP ist beim SchmeNm-Cd strikter |

### 16. CGI-MP Relay zu CBPR+ — Zusatzkapitel

CGI-MP definiert ein **Relay-Szenario**, in dem ein Forwarding Agent eine CGI-MP pain.001 vom Corporate empfaengt und sie als CBPR+ pain.001 an die Debtor Bank weiterleitet:

```
Corporate --[CGI-MP pain.001]--> Forwarding Agent --[CBPR+ pain.001]--> Debtor Agent --[pacs.008]--> Creditor Agent
```

Wesentliche Aktionen des Forwarding Agents:
- BAH (head.001.001.02) hinzufuegen (CBPR+ Pflicht, CGI-MP existiert nicht)
- Multi-Tx splitten (CBPR+ erlaubt nur 1 Tx pro Message)
- MsgId ggf. ersetzen (Eindeutigkeit im CBPR+ Netz)
- UETR generieren wenn nicht vorhanden (CBPR+ Pflicht)
- Charset konvertieren (CBPR+ FIN-X ist restriktiver als CGI-MP UTF-8)
- Hybrid-Adressen ggf. zu unstrukturiert mappen (bis Nov 2025)

SPS 2025 hat **kein analoges Relay-Konzept**, da SPS ein End-Standard fuer den Schweizer Markt ist und nicht als Vorstufe zu CBPR+ dient.

## Konsequenzen fuer unseren Code

| Aspekt | Aktueller Stand | Bemerkung |
|--------|-----------------|-----------|
| **Standard-Auswahl** | Excel-Spalte `Standard` (`sps2025` / `cgi-mp` / `cbpr+2026`) | Pro Testfall waehlbar |
| **Charset-Sanitization** | Aktuell: `^[a-zA-Z0-9 /\-?:().,'+]*$` (Reference Charset, ASCII-only) | Stricter als die SPS-IG fuer normale Textfelder, **fuer CGI-MP zu streng** (CGI-MP erlaubt UTF-8 voll) |
| **Empty Tags** | Werden vom Builder vermieden | OK fuer CGI-MP |
| **Address-Formate** | Strukturiert + hybrid + unstrukturiert | OK fuer beide; strukturiert ist Default |
| **`BR-CGI-ADDR-02`** | Implementiert: UltmtDbtr/UltmtCdtr/InitgPty muessen strukturiert sein | OK |
| **`BR-CGI-PURP-01/02`** | Implementiert: RgltryRptg verlangt DbtCdtRptgInd, Purpose darf nicht in `Purp` wenn regulatorisch | OK |
| **`BR-CGI-PMTMTD-01`** | Implementiert: PmtMtd muss TRF sein (Non-Cheque) | OK |
| **`BR-CGI-ORG-01`** | Implementiert: OrgId/Othr/SchmeNm nur `Cd`, kein `Prtry` | OK |
| **`BR-CGI-SEPA-SVC-01`** | Implementiert: CGI-MP+SEPA verlangt `SvcLvl/Cd=SEPA` | OK |
| **`BR-CGI-PTI-01`** | Implementiert: wenn PmtTpInf emittiert, SvcLvl Pflicht | OK |
| **`BR-CGI-CHAR-01`** | Implementiert: keine leeren Tags | OK |
| **`BR-CGI-RMT-01..03`** | Implementiert: Structured/Unstructured Exclusivity, max 9000 Zeichen Strd, RfrdDocInf Type Pflicht | OK |
| **`BR-CGI-TAX-01..03`** | Implementiert: WHLD verlangt Tax-Element, beide TaxIDs Pflicht, Method Pflicht | OK |
| **`BR-CGI-RGRP-01/02`** | Implementiert: Dtls verlangt Tp, Code max 10 Zeichen | OK |

## Empfehlungen fuer Weiterentwicklung

1. **Charset-Sanitization auflockern fuer CGI-MP**: aktuell wird der ASCII-only Reference-Charset auch fuer normale Textfelder angewandt. Fuer CGI-MP-Testfaelle sollte UTF-8 voll erlaubt sein (z.B. CJK-Namen, kyrillische Adressen) und nur die Reference-Felder (MsgId, PmtInfId, InstrId, EndToEndId) ASCII-restringiert bleiben.
2. **`vergleich-sps-epc-sepa-2025.md`** ergaenzen mit einem expliziten Vergleichsabschnitt zu CGI-MP (analog zu diesem Dokument fuer SPS).
3. **CGI-MP Relay-Modus**: Falls perspektivisch ein Relay-Use-Case unterstuetzt werden soll (CGI-MP→CBPR+ Konversion), siehe `docs/roadmap/2026-04-06_pain001_pacs008_chain_analysis.md`.

## Quellenverzeichnis

- SPS 2025 IG, Kapitel 3.1 (Zeichensatz), 3.4 (leere Elemente), 3.11 (Adressen), 4.3 C-Level Felder
- SPS 2025 Business Rules v3.2, Kategorien CH21, BR-CBPR-*, BR-CGI-*
- CGI-MP WG1 User Handbook Nov 2025: Slides 4 (Charset), 6-11 (Adressen), 12-13 (Purpose), 14-22 (RgltryRptg), 23-38 (Remittance), 39-51 (Tax), 52-57 (Relay)
- CGI-MP Appendix B (Local Country Rules, RgltryRptg-Tabellen)
