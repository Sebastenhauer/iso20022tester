# pacs.008 Implementation Guide

**Version:** 1.0 (Ergebnis der 13 WPs aus `docs/roadmap/2026-04-06_pacs008_implementation_plan.md`)
**Datum:** 2026-04-06
**Flavor:** CBPR+ SR2026 (pacs.008.001.08). TARGET2/SEPA/SIC-Flavors sind im Datenmodell vorbereitet aber noch nicht aktiv.

## Architektur-Ueberblick

Zwei parallele Pipelines teilen sich gemeinsame Infrastruktur (DataFactory, IBAN-Generator, BIC-Directory, XSD-Validator, Reporter, Excel-Parser-Framework, external XML Validator service-Client). Der CLI-Dispatch auf den richtigen Pfad passiert per Header-Auto-Detection in `src/input_handler/excel_parser.py::detect_message_type`.

```
src/
├── pipeline.py                         # pain.001 Pipeline
├── pacs008_pipeline.py                 # pacs.008 Pipeline (WP-08)
├── main.py                             # Unified CLI mit --message Flag
│
├── models/
│   ├── testcase.py                     # pain.001 Modelle
│   └── pacs008.py                      # pacs.008 Modelle (WP-02)
│
├── xml_generator/
│   ├── builders.py                     # pain.001 Element-Builder
│   ├── pain001_builder.py              # pain.001 Assembly
│   ├── bah_builder.py                  # BAH fuer pain.001 (unveraendert)
│   └── pacs008/                        # pacs.008 Subpackage (WP-05)
│       ├── namespaces.py               #   Namespace-Konstanten
│       ├── builders.py                 #   Element-Builder
│       └── message_builder.py          #   Document + BAH Assembly
│
├── payment_types/
│   ├── base.py, sepa.py, ...           # pain.001 Handler
│   └── pacs008/
│       └── defaults.py                 # Default-Werte (WP-04)
│
├── validation/
│   ├── rule_catalog.py                 # Unified Rule-Catalog (alle Messages)
│   ├── business_rules.py               # pain.001 Rule Executor
│   ├── pacs008_rules.py                # pacs.008 Rule Executor (WP-06)
│   └── pacs008_violations.py           # pacs.008 Violations Registry (WP-07)
│
├── input_handler/
│   └── excel_parser.py                 # Auto-Detection + parse_pacs008_excel (WP-03)
│
└── xml_validator/
    └── client.py                       # XML Validator API Client (WP-09)
```

## Datenmodell (WP-02)

```
Pacs008TestCase                     Input-Layer (aus Excel)
    |
    V
Pacs008BusinessMessage              Envelope (BAH + Document)
    ├── bah_from_bic                  (Fr)
    ├── bah_to_bic                    (To)
    ├── bah_biz_msg_idr               (BizMsgIdr)
    ├── bah_msg_def_idr               (MsgDefIdr = pacs.008.001.08)
    ├── bah_biz_svc                   (BizSvc = swift.cbprplus.02)
    ├── bah_cre_dt                    (CreDt, mit TZ-Offset)
    └── instruction: Pacs008Instruction
        ├── msg_id                    (GrpHdr/MsgId)
        ├── cre_dt_tm                 (GrpHdr/CreDtTm, mit TZ-Offset)
        ├── number_of_transactions    (GrpHdr/NbOfTxs)
        ├── control_sum               (Sum-Check, CBPR+ hat kein CtrlSum)
        ├── interbank_settlement_date (C-Level IntrBkSttlmDt)
        ├── settlement_method         (SettlementMethod Enum: INDA/INGA/COVE)
        ├── settlement_account        (optional SttlmInf/SttlmAcct)
        ├── instructing_agent         (wird auf C-Level emittiert, nicht GrpHdr)
        ├── instructed_agent          (C-Level)
        └── transactions[]: Pacs008Transaction
            ├── instruction_id        (PmtId/InstrId, max 16 Zeichen)
            ├── end_to_end_id         (PmtId/EndToEndId)
            ├── uetr                  (PmtId/UETR, Pflicht UUIDv4)
            ├── instructed_amount     (InstdAmt)
            ├── instructed_currency   (InstdAmt.Ccy)
            ├── interbank_settlement_amount (optional)
            ├── charge_bearer         (ChrgBr)
            ├── charges_info[]        (ChrgsInf Liste, kein Default)
            ├── debtor: PartyInfo
            ├── debtor_account: AccountInfo
            ├── debtor_agent: AgentInfo
            ├── creditor: PartyInfo
            ├── creditor_account: AccountInfo
            ├── creditor_agent: AgentInfo
            ├── intermediary_agents[]: AgentInfo  (IntrmyAgt1/2/3)
            ├── previous_instructing_agents[]: AgentInfo
            ├── ultimate_debtor: PartyInfo (optional)
            ├── ultimate_creditor: PartyInfo (optional)
            ├── purpose_code          (Purp/Cd)
            ├── category_purpose      (PmtTpInf/CtgyPurp/Cd)
            ├── service_level         (PmtTpInf/SvcLvl/Cd)
            ├── local_instrument      (PmtTpInf/LclInstrm/Cd)
            ├── remittance_info       ({"type": "USTRD", "value": "..."})
            ├── regulatory_reporting  (dict, Keys analog pain.001)
            └── overrides             (Dot-Notation-Overrides)
```

### Leaf-Objekte

| Objekt | Beschreibung |
|---|---|
| `PostalAddress` | StrtNm, BldgNb, PstCd, TwnNm, Ctry (strukturiert) |
| `AgentInfo` | bic XOR/AND (clearing_system_code + clearing_member_id), + Nm, PstlAdr |
| `AccountInfo` | iban OR (other_id + other_scheme_code), optional currency |
| `PartyInfo` | name + postal_address + lei + organisation_other_id |
| `ChargesInfo` | amount + currency + agent (AgentInfo) |

## Builder-Reihenfolge (strikt nach CBPR+ SR2026 XSD)

```python
# src/xml_generator/pacs008/builders.py::build_cdt_trf_tx_inf

<CdtTrfTxInf>
    <PmtId>                            # 1. PmtId mit InstrId (Pflicht), EndToEndId, UETR
        <InstrId>INSTR<hex8></InstrId>
        <EndToEndId>...</EndToEndId>
        <UETR>uuid-v4</UETR>
    </PmtId>
    <PmtTpInf>                         # 2. Optional: SvcLvl, LclInstrm, CtgyPurp
        ...
    </PmtTpInf>
    <IntrBkSttlmAmt Ccy="EUR">...</>   # 3. IntrBkSttlmAmt (currency-aware formatting)
    <IntrBkSttlmDt>2026-04-08</>       # 4. IntrBkSttlmDt (T+1 default)
    <InstdAmt Ccy="EUR">...</>         # 5. InstdAmt
    <ChrgBr>SHAR</ChrgBr>              # 6. ChrgBr (Pflicht)
    <ChrgsInf>...</ChrgsInf>           # 7. ChrgsInf* (optional, 0..unbounded)
    <PrvsInstgAgt1>...</>              # 8. PrvsInstgAgt1/2/3 (optional)
    <InstgAgt>...</InstgAgt>           # 9. InstgAgt (C-Level Pflicht in CBPR+)
    <InstdAgt>...</InstdAgt>           # 10. InstdAgt (C-Level Pflicht)
    <IntrmyAgt1>...</IntrmyAgt1>       # 11. IntrmyAgt1/2/3 (optional)
    <UltmtDbtr>...</UltmtDbtr>         # 12. Optional
    <Dbtr>...</Dbtr>                   # 13. Pflicht
    <DbtrAcct>...</DbtrAcct>           # 14. Optional
    <DbtrAgt>...</DbtrAgt>             # 15. Pflicht
    <CdtrAgt>...</CdtrAgt>             # 16. Pflicht
    <Cdtr>...</Cdtr>                   # 17. Pflicht
    <CdtrAcct>...</CdtrAcct>           # 18. Optional
    <UltmtCdtr>...</UltmtCdtr>         # 19. Optional
    <Purp>...</Purp>                   # 20. Optional
    <RmtInf>...</RmtInf>               # 21. Optional
</CdtTrfTxInf>
```

## Business Rules

Rule-Familie `BR-CBPR-PACS-001..015`. Der Rule-Catalog unterscheidet die pacs.008-Rules von der pain.001-Familie ueber die Kategorie `CBPR-PACS`.

Vollstaendige Liste mit Beschreibungen siehe README.md oder `src/validation/rule_catalog.py`.

## Currency-Aware Amount Formatting

Die Funktion `_fmt_amount(amount, currency)` in `src/xml_generator/pacs008/builders.py` respektiert ISO 4217:

| Dezimalstellen | Currencies |
|---|---|
| 0 | BIF, CLP, DJF, GNF, ISK, JPY, KMF, KRW, PYG, RWF, UGX, UYI, VND, VUV, XAF, XOF, XPF |
| 2 | EUR, USD, GBP, CHF, CAD, AUD, SGD, HKD, CNY, ... (default) |
| 3 | BHD, IQD, JOD, KWD, LYD, OMR, TND |

Dieser Check wurde durch eine External-Validation (WP-12 Runde 1, TC-PCS-004 JPY) aufgedeckt und ist per Unit Test (`tests/test_pacs008_amount_formatting.py`) gegen Regression geschuetzt.

## Default-Werte (WP-04)

`src/payment_types/pacs008/defaults.py::apply_defaults_to_testcase(tc)` mutiert ein `Pacs008TestCase` in-place:

| Feld | Default | Bedingung |
|---|---|---|
| `charge_bearer` | `SHAR` | wenn None |
| `interbank_settlement_date` | T+1 business day | wenn None; TARGET2 fuer EUR, Switzerland sonst |
| `intermediary_agent_1_bic` | `CHASUS33XXX` | wenn alle drei IntrmyAgt-Slots leer UND flavor=CBPR+ |

**Keine** Defaults fuer:
- `instructing_agent_bic`, `instructed_agent_bic`, `debtor_agent_bic`, `creditor_agent_bic` (muss User setzen)
- `charges_info` (keine automatischen ChrgsInf-Eintraege)

## Violations Registry (WP-07)

Negative Testing via `ViolateRule`-Spalte im Excel. Die Violations-Funktionen mutieren eine gueltige `Pacs008BusinessMessage` vor dem XML-Build, sodass eine spezifische Rule gezielt fehlschlaegt.

Verfuegbar in `src/validation/pacs008_violations.py::get_pacs008_violations_registry()`:

- BR-CBPR-PACS-001 → UETR clearen
- BR-CBPR-PACS-002 → InstgAgt ohne Identifikation
- BR-CBPR-PACS-003 → InstdAgt ohne Identifikation
- BR-CBPR-PACS-004 → SttlmMtd=COVE
- BR-CBPR-PACS-007 → BAH MsgDefIdr auf falsche Version
- BR-CBPR-PACS-008 → BAH BizSvc faelschen
- BR-CBPR-PACS-010 → ChrgBr=XXXX
- BR-CBPR-PACS-011 → Currency=X9X
- BR-CBPR-PACS-015 → UETR auf Non-UUIDv4

## XML Validator integration (WP-09, WP-11)

Siehe [`docs/xml_validator_integration.md`](xml_validator_integration.md).

## Testing

- **Unit Tests:** 797 tests (neue pacs.008-Tests + bestehende pain.001)
- **Integration Tests:** `tests/test_pacs008_pipeline.py` fuer End-to-End Pipeline
- **XSD Round-Trip:** `tests/test_pacs008_builders.py::test_minimal_document_is_xsd_valid` validiert gegen das echte CBPR+ SR2026 Schema
- **Lokaler Full-Run:** `templates/testfaelle_pacs008_comprehensive.xlsx` — 50/50 Pass

## Bekannte Einschraenkungen (V1)

- **Single Transaction per Message:** CBPR+ erlaubt nur 1 CdtTrfTxInf pro Nachricht (XSD-Constraint). Multi-Tx-Batching ist nicht vorgesehen.
- **COVE Settlement Method:** out of scope (verlangt begleitende pacs.009 Cover-Nachricht).
- **Overrides anwenden:** die `Weitere Testdaten`-Column wird vom Parser gelesen und ins `overrides`-Dict uebertragen, aber der pacs.008-Pipeline-Builder wendet die Overrides derzeit nicht auf die generierte XML an. Das ist eine V1-Einschraenkung; gezielte Ueberschreibung von z.B. `UltmtDbtr.Nm` muss aktuell ueber erweiterte Excel-Spalten oder Codeaenderungen passieren.
- **Chain-Derivation pain.001→pacs.008:** out of scope (siehe `docs/roadmap/2026-04-06_pain001_pacs008_chain_analysis.md`).
- **Correspondent-Lookup-Map:** out of scope (siehe `docs/roadmap/2026-04-06_correspondent_lookup_map.md`).
- **TARGET2/SEPA/SIC Flavors:** Datenmodell und external XML Validator service-Endpoint-Dispatch sind vorbereitet, aber keine spezifischen Builder oder Business Rules.
