# Deep-Dive Task: pain.001 → pacs.008 Chain-Derivation

**Erstellt:** 2026-04-06
**Status:** Out of scope (V1 pacs.008)
**Priorität:** Mittel, zur späteren Analyse
**Verwandt:** pacs.008 Initial Implementation (V1)

## Hintergrund

Das Repo soll in V1 pacs.008 unabhängig von pain.001 generieren (eigene Test-Cases, eigenes Excel). Der logisch naheliegende nächste Schritt ist die **automatische Ableitung** einer pacs.008-Nachricht aus einer existierenden pain.001-Zeile: "Wenn Bank X diese pain.001 erhält, welche pacs.008 würde sie an Bank Y weiterreichen?". Das ermöglicht End-to-End-Chain-Tests ohne dass der User zwei Excels pflegen muss.

## Warum out of scope für V1

- pain.001 und pacs.008 haben unterschiedliche Pflichtfelder; eine 1:1-Ableitung ist unvollständig und verlangt Zusatz-Annahmen (Instructing Agent, Instructed Agent, Intermediary-Kette, Settlement-Method).
- Default-Mapping-Logik muss ausführlich mit Domain-Experten abgestimmt werden (welche Felder der DebtorAgent aus pain.001 welche in pacs.008 befüllen, speziell bei Cover vs Serial, IntrBkSttlmDt-Ableitung aus ReqdExctnDt minus Cut-Off, Charges-Propagation SHAR→DEBT/CRED, etc.).
- Erst sinnvoll wenn V1 pacs.008 stabil läuft und Business-Rules gegen FINaplo verifiziert sind.

## Zu klärende Fragen (Deep-Dive)

### Konzeptionell
1. Aus welcher Rolle heraus leiten wir ab: Debtor Agent → Correspondent → Creditor Agent? Beliebiger Hop?
2. Ist die Ableitung **deterministisch** (gleiche pain.001 → exakt gleiche pacs.008) oder hat sie freie Parameter (z.B. Cover vs Serial Wahl)?
3. Soll das Mapping in `config.yaml` konfigurierbar sein (z.B. "unsere Bank ist BIC X, bei Cross-Border nutzen wir Correspondent Y in USD, Z in EUR")?
4. End-to-end Scope: nur pain.001→pacs.008, oder auch pacs.008→pacs.002 (Statusbericht)?

### Datenfluss
5. Welche Felder werden direkt übernommen (Cdtr Name, Cdtr Addr, Amt, RmtInf, UETR)?
6. Welche Felder müssen neu berechnet werden (IntrBkSttlmDt aus ReqdExctnDt; InstdAmt → IntrBkSttlmAmt; Debtor aus pain.001 bleibt, aber DebtorAgent wird der Prozessor)?
7. Welche Felder werden **komplett neu erzeugt** (MsgId pacs.008, InstrId am C-Level, AppHdr BizMsgIdr, UETR propagiert oder neu?)?
8. Wie werden Charges-Änderungen behandelt (SHAR aufgeteilt wird zu zwei `ChrgsInf`-Einträgen)?

### Multi-Hop / Correspondent
9. Wenn der Cross-Border-Hop über eine Correspondent Bank geht (IntrmyAgt1), soll das Config-getrieben sein (Mapping-Tabelle pro Currency/Country)?
10. Serial vs Cover: soll der Chain-Generator automatisch entscheiden (z.B. basierend auf Currency-Corridor), oder explizit via Excel-Flag?

### Excel / UX
11. Neue Spalte "ChainFromPain001=TC-ID-XYZ" die die Quell-pain.001-Zeile referenziert?
12. Oder ein eigener CLI-Befehl `python -m src.main --chain --source-pain templates/pain001.xlsx --target-pacs templates/pacs008_derived.xlsx`?
13. Sollen die abgeleiteten pacs.008 in ein **automatisch generiertes** Excel geschrieben werden (für späteren Replay), oder nur on-the-fly bei Run-Zeit erzeugt werden?

### Testen
14. Wie verifiziert man die Korrektheit einer Chain-Derivation? Referenz-Paare aus SWIFT-Dokumentation? Manuelle Review?
15. Soll es einen Snapshot-Test pro Chain-Rule geben?

### Tooling
16. Gibt es Open-Source-Implementierungen von pain.001→pacs.008-Mapping, die wir als Referenz nutzen können? (Payment Components, Prowide, XMLdation?)
17. Bietet FINaplo eine Chain-Derivation-API oder nur Validation?

## Nächste Schritte (wenn Task aufgegriffen wird)

1. Beantwortung obiger 17 Fragen mit User
2. Erstellung eines "Mapping Specification Document" mit Zeilen-für-Zeile Regel
3. Prototype-Implementation als `src/chain/pain001_to_pacs008.py`
4. Unit Tests gegen 5–10 Referenz-Paare
5. Integration in unified CLI via `--chain` Modus
6. Dokumentation in `docs/chain_derivation.md`

## Geschätzter Aufwand

- Analyse + Mapping-Spec: 1–2 Tage mit Domain-Expertise
- Prototype-Code: 2–3 Tage
- Tests + Dokumentation: 1 Tag
- Total: ~1 Woche Arbeit, aber nur sinnvoll wenn V1 pacs.008 produktiv läuft

## Referenzen

- `docs/specs/pacs.008/cbpr+nonpublic/CBPR+ User Handbook 2025.pdf` (SWIFT CBPR+ Handbook)
- `docs/specs/pain.001/ig-credit-transfer-sps-2025-de.md`
- Verwandte Diskussion: Session 2026-04-06 (User-Frage nach 20 Rückfragen zur pacs.008-Implementation)
