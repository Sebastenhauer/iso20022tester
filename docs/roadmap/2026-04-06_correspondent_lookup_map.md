# Roadmap-Idee: Correspondent Bank Lookup Map

**Erstellt:** 2026-04-06
**Status:** Out of scope für pacs.008 V1; zur späteren Umsetzung vorgemerkt
**Verwandt:** pacs.008 Implementation V1 (Intermediary Agent Defaulting)

## Idee

Für pacs.008-Nachrichten mit Intermediary Agents (`IntrmyAgt1/2/3`) soll es optional eine **Correspondent-Lookup-Tabelle** geben, die pro Currency- oder Country-Corridor einen sinnvollen Default-Korrespondenten liefert, wenn der User im Excel keine Intermediary Agents explizit angibt.

## Aktuelles Verhalten in V1

In V1 wird per Default **genau ein Intermediary Agent** gesetzt — ein fixer Wert aus `src/payment_types/pacs008/defaults.py`, unabhängig vom Zielkorridor. Der User kann diesen Default über das Excel-Feld `Weitere Testdaten` via Dot-Notation (`IntrmyAgt1.FinInstnId.BICFI=...`) überschreiben. Für realistische Szenarien müsste der User jeden Testfall einzeln konfigurieren.

## Vorgeschlagene Erweiterung

**Entscheid (2026-04-06):** Umsetzung als **statische Python-Liste/Dict**, die inline im Code dokumentiert ist und vom User jederzeit durch Edit und Re-Run erweitert werden kann. **Keine** YAML-Konfiguration in V1 — das wäre Over-Engineering. Die Datei soll so strukturiert sein, dass Hinzufügen neuer Einträge trivial ist (Copy-Paste einer Zeile).

Eine **statische Mapping-Tabelle**:

```python
CORRESPONDENT_MAP = {
    # Corridor (debtor_country, creditor_country, currency) -> (bic_list)
    ("CH", "US", "USD"): ["CHASUS33XXX"],           # JPMorgan NYC
    ("CH", "GB", "GBP"): ["HSBCGB2LXXX"],
    ("CH", "JP", "JPY"): ["BOFAJPJXXXX"],
    ("CH", "CN", "CNY"): ["ICBKCNBJXXX"],
    # Multi-hop
    ("CH", "BR", "BRL"): ["CHASUS33XXX", "ITAUBRSPXXX"],
    # etc.
}
```

~~Alternativ: YAML-Konfiguration~~ — verworfen (2026-04-06), siehe Entscheid oben.

## Resolution-Logik

1. Wenn User `IntrmyAgt1/2/3` im Excel explizit angibt → diese verwenden (höchste Prio)
2. Wenn nicht → Lookup über `(debtor_country, creditor_country, currency)`
3. Wenn kein Match → Lookup nur über `currency`
4. Wenn kein Match → globaler Default aus `defaults.py`
5. Wenn auch kein globaler Default → **kein** Intermediary Agent im XML

## Zusatznutzen

- **Realistische Testcases** ohne dass der User pro Row einen BIC recherchieren muss
- **Edukativer Wert**: zeigt welcher Korridor welche Routing-Bank nutzt
- **external XML Validator service-Compliance**: realistische BIC-Kombinationen schlagen weniger Validation-Warnungen aus
- **Simulation von Multi-Hop**: wenn ein Korridor mehrere Intermediaries braucht (z.B. Exotic Currency über USD-Clearing), kann die Map das modellieren

## Fragen für Deep-Dive

1. Woher kommen die Default-BICs? Public-Domain-Knowledge, SWIFT BIC Directory (bei uns als CSV schon optional hinterlegt via `bic_directory_path`), manuell kuratiert?
2. Soll die Map **bidirektional** sein (Outflow und Inflow)?
3. Wie verhalten wir uns bei seltenen Corridors ohne Match? Warning loggen? Default fallback?
4. Soll es eine **Override-Kaskade** mit Wildcards geben (z.B. `* -> CNY: ICBKCNBJXXX`)?
5. Integration mit einer externen Quelle (z.B. SWIFT BIC directory download, Wise API)?
6. Laufende Pflege: wer hält die Map aktuell?

## Umsetzungs-Aufwand

- Minimal (statischer Dict, 20 Corridors): 0.5 Tage
- Mit YAML-Config, CLI-Override, Fallback-Logik, Unit-Tests: 1.5 Tage
- Mit externer Quelle (BIC-Directory-Integration): +1 Tag

## Priorität

**Mittel.** Erst sinnvoll, wenn V1 pacs.008 stabil läuft und User tatsächlich mit Intermediary-Szenarien arbeitet. Bis dahin reicht der User-Override via `Weitere Testdaten`.

## Referenzen

- Session 2026-04-06: pacs.008 V1 Implementation Planning
- Verwandte Roadmap: `docs/roadmap/2026-04-06_pain001_pacs008_chain_analysis.md`
- `src/payment_types/pacs008/defaults.py` (wird in V1 erstellt, initial ohne Map)
