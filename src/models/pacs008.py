"""Datenmodelle fuer pacs.008 (FI-to-FI Customer Credit Transfer).

Eigenstaendige Modell-Familie parallel zu pain.001 (`src/models/testcase.py`).
V1 unterstuetzt den Flavor ``CBPR_PLUS`` (SR2026, pacs.008.001.08);
weitere Flavors (TARGET2, SEPA, SIC) sind per Enum vorbereitet, aber
nicht implementiert.

Design-Entscheidungen (siehe docs/roadmap/2026-04-06_pacs008_implementation_plan.md):

- Keine Wiederverwendung von TestCase/PaymentInstruction aus pain.001.
- Agenten-Kette via ``intermediary_agents: List[AgentInfo]`` (bis zu 3 Hops).
- Charges-Info explizit pro Hop als Liste von ``ChargesInfo``-Objekten;
  *keine* Default-Werte wenn der User nichts mitgibt.
- ``pacs008_flavor`` bestimmt spaeter den FINaplo-Endpoint
  (``CBPR_PLUS`` -> ``/cbpr/validate``).
- Felder im BAH (AppHdr) werden separat am TestCase gehalten
  (``bah_from_bic`` / ``bah_to_bic``), da sie logisch nicht zur
  Instruction, sondern zum Envelope gehoeren.
"""

from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from src.models.testcase import ExpectedResult


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Pacs008Flavor(str, Enum):
    """Implementation-Flavor fuer pacs.008.

    In V1 wird nur ``CBPR_PLUS`` implementiert. Die anderen Werte sind
    vorbereitet fuer spaetere Implementationen und dienen schon jetzt
    der FINaplo-Endpoint-Auswahl (`/cbpr/validate` vs `/target2/validate`
    vs `/sepa/{scheme}/validate`).
    """

    CBPR_PLUS = "CBPR+"
    TARGET2 = "TARGET2"
    SIC = "SIC"
    SEPA = "SEPA"


class SettlementMethod(str, Enum):
    """SttlmInf/SttlmMtd-Werte nach ISO 20022 ExternalSettlementMethod1Code."""

    INDA = "INDA"  # Instructed Agent settles
    INGA = "INGA"  # Instructing Agent settles
    CLRG = "CLRG"  # Clearing System
    COVE = "COVE"  # Cover Method (out of scope V1)


# ---------------------------------------------------------------------------
# Leaf-Objekte
# ---------------------------------------------------------------------------

class PostalAddress(BaseModel):
    """Strukturierte Postadresse (PstlAdr) gemaess ISO 20022.

    Freie Subset-Auswahl; weitere Felder (Dept, SubDept, Flr, PstBx,
    BldgNm, DstrctNm, CtrySubDvsn) koennen bei Bedarf ergaenzt werden.
    """

    street_name: Optional[str] = None
    building_number: Optional[str] = None
    postal_code: Optional[str] = None
    town_name: Optional[str] = None
    country: Optional[str] = None  # ISO 3166-1 alpha-2

    def is_empty(self) -> bool:
        return not any(
            [self.street_name, self.building_number, self.postal_code,
             self.town_name, self.country]
        )


class AgentInfo(BaseModel):
    """Finanzinstitut-Identifikation (BICFI oder Clearing-System-Member-ID).

    Mindestens eines von ``bic`` oder ``clearing_member_id`` muss gesetzt
    sein; beides gleichzeitig ist erlaubt (ISO 20022 laesst beide
    FinInstnId-Kinder zu).
    """

    bic: Optional[str] = None
    name: Optional[str] = None
    postal_address: Optional[PostalAddress] = None
    clearing_system_code: Optional[str] = None  # z.B. USABA, CHBCC, CHAPS
    clearing_member_id: Optional[str] = None

    @property
    def is_bic_only(self) -> bool:
        return bool(self.bic) and not self.clearing_member_id

    @property
    def has_identification(self) -> bool:
        return bool(self.bic) or bool(self.clearing_member_id)


class AccountInfo(BaseModel):
    """Konto-Identifikation (IBAN oder Othr)."""

    iban: Optional[str] = None
    other_id: Optional[str] = None
    other_scheme_code: Optional[str] = None  # ExternalAccountIdentification1Code
    currency: Optional[str] = None

    @property
    def has_id(self) -> bool:
        return bool(self.iban) or bool(self.other_id)


class PartyInfo(BaseModel):
    """Party-Identifikation (Debtor, Creditor, Ultimate-*)."""

    name: str
    postal_address: Optional[PostalAddress] = None
    lei: Optional[str] = None
    organisation_other_id: Optional[str] = None
    organisation_other_scheme: Optional[str] = None  # Standard: "LEI" oder Externes Cd
    country_of_residence: Optional[str] = None


class ChargesInfo(BaseModel):
    """Gebuehren pro Hop (`ChrgsInf`).

    Laut CBPR+ IG ist `Amt` + `Agt` Pflicht, wenn ChrgsInf vorhanden ist.
    """

    amount: Decimal = Field(..., decimal_places=2)
    currency: str  # ISO 4217
    agent: AgentInfo  # Agent der die Gebuehren traegt (FinInstnId)


# ---------------------------------------------------------------------------
# Transaction & Instruction
# ---------------------------------------------------------------------------

class Pacs008Transaction(BaseModel):
    """Eine CdtTrfTxInf-Zeile innerhalb einer pacs.008-Nachricht."""

    # Identifikation
    instruction_id: Optional[str] = None
    end_to_end_id: str
    tx_id: Optional[str] = None
    uetr: str  # Pflicht laut CBPR+

    # Betrag & Settlement
    instructed_amount: Decimal = Field(..., decimal_places=2)
    instructed_currency: str  # ISO 4217
    interbank_settlement_amount: Optional[Decimal] = Field(None, decimal_places=2)
    interbank_settlement_currency: Optional[str] = None
    charge_bearer: Optional[str] = None  # DEBT/CRED/SHAR

    # Charges-Details pro Hop (keine Defaults, nur wenn explizit)
    charges_info: List[ChargesInfo] = []

    # Parties (C-Level)
    debtor: PartyInfo
    debtor_account: Optional[AccountInfo] = None
    debtor_agent: AgentInfo
    creditor_agent: AgentInfo
    creditor: PartyInfo
    creditor_account: Optional[AccountInfo] = None

    # Optional
    ultimate_debtor: Optional[PartyInfo] = None
    ultimate_creditor: Optional[PartyInfo] = None
    previous_instructing_agents: List[AgentInfo] = []  # PrvsInstgAgt1..3
    intermediary_agents: List[AgentInfo] = []          # IntrmyAgt1..3
    purpose_code: Optional[str] = None  # Purp/Cd
    category_purpose: Optional[str] = None  # PmtTpInf/CtgyPurp/Cd
    service_level: Optional[str] = None  # PmtTpInf/SvcLvl/Cd
    local_instrument: Optional[str] = None  # PmtTpInf/LclInstrm/Cd

    # Remittance
    remittance_info: Optional[Dict[str, str]] = None  # {"type": "USTRD", "value": "..."}
    regulatory_reporting: Optional[Dict[str, str]] = None

    # Free-form Overrides (Dot-Notation), werden im Builder angewandt
    overrides: Dict[str, str] = {}


class Pacs008Instruction(BaseModel):
    """Vollstaendige pacs.008-Nachricht (GrpHdr + 1..N CdtTrfTxInf).

    Die BAH-Felder (AppHdr) werden separat im TestCase gehalten;
    diese Instruction repraesentiert nur das <Document>.
    """

    msg_id: str
    cre_dt_tm: str  # ISO 8601
    number_of_transactions: int  # NbOfTxs (wird aus transactions.len abgeleitet)
    control_sum: Decimal = Field(..., decimal_places=2)
    interbank_settlement_date: str  # IntrBkSttlmDt (YYYY-MM-DD)

    # Group-Header Agents (oft identisch mit dem ersten DbtrAgt/CdtrAgt Hop)
    instructing_agent: AgentInfo
    instructed_agent: AgentInfo

    # Settlement Info (B-Level des pacs.008 ist GrpHdr/SttlmInf)
    settlement_method: SettlementMethod = SettlementMethod.INDA
    settlement_account: Optional[AccountInfo] = None

    transactions: List[Pacs008Transaction]


class Pacs008BusinessMessage(BaseModel):
    """Container aus <AppHdr> (BAH, head.001.001.02) + <Document> (pacs.008).

    Wird beim Serialisieren zu einem einzigen XML-File im
    BusinessMessage-Envelope zusammengefuegt. Intern bleiben BAH und
    Document getrennt, damit der Code sauber pruefbar ist.
    """

    bah_from_bic: str
    bah_to_bic: str
    bah_biz_msg_idr: str  # typischerweise msg_id der Instruction
    bah_msg_def_idr: str = "pacs.008.001.08"
    bah_biz_svc: str = "swift.cbprplus.02"
    bah_cre_dt: str  # ISO 8601

    instruction: Pacs008Instruction


# ---------------------------------------------------------------------------
# TestCase
# ---------------------------------------------------------------------------

class Pacs008TestCase(BaseModel):
    """Testfall fuer pacs.008 aus dem Excel.

    Input-Datenstruktur vor Pipeline-Ausfuehrung. Die Pipeline baut aus
    einem TestCase eine oder mehrere ``Pacs008Instruction``-Instanzen
    (mit angewandten Defaults + Violations) und serialisiert sie dann
    als BusinessMessage.
    """

    testcase_id: str
    titel: str
    ziel: str
    expected_result: ExpectedResult
    flavor: Pacs008Flavor = Pacs008Flavor.CBPR_PLUS

    # BAH-Felder (getrennt von der Instruction gehalten)
    bah_from_bic: Optional[str] = None
    bah_to_bic: Optional[str] = None

    # GrpHdr-Agents (Fallback: gleich den B-Level-DbtrAgt/CdtrAgt)
    instructing_agent_bic: Optional[str] = None
    instructing_agent_clr_sys_mmb_id: Optional[str] = None
    instructed_agent_bic: Optional[str] = None
    instructed_agent_clr_sys_mmb_id: Optional[str] = None

    # Settlement
    settlement_method: SettlementMethod = SettlementMethod.INDA
    interbank_settlement_date: Optional[str] = None  # leer -> via defaults resolved

    # Payment-Level Defaults (B-Level)
    charge_bearer: Optional[str] = None

    # Vereinfachter Single-Tx-Fall (pacs.008 kann Batch, V1 fokussiert 1 Tx/Msg)
    # Fuer Multi-Tx wird ``transaction_rows`` genutzt (spaetere Ausbaustufe).
    debtor_name: Optional[str] = None
    debtor_address: Optional[PostalAddress] = None
    debtor_iban: Optional[str] = None
    debtor_account_other_id: Optional[str] = None
    debtor_account_other_scheme: Optional[str] = None
    debtor_agent_bic: Optional[str] = None
    debtor_agent_clr_sys_mmb_id: Optional[str] = None

    creditor_name: Optional[str] = None
    creditor_address: Optional[PostalAddress] = None
    creditor_iban: Optional[str] = None
    creditor_account_other_id: Optional[str] = None
    creditor_account_other_scheme: Optional[str] = None
    creditor_agent_bic: Optional[str] = None
    creditor_agent_clr_sys_mmb_id: Optional[str] = None

    # Intermediary Agents (BICs, optional ClrSysMmbId per Dot-Notation)
    intermediary_agent_1_bic: Optional[str] = None
    intermediary_agent_1_clr_sys_mmb_id: Optional[str] = None
    intermediary_agent_2_bic: Optional[str] = None
    intermediary_agent_3_bic: Optional[str] = None

    # Amount & Currency
    amount: Optional[Decimal] = Field(None, decimal_places=2)
    currency: Optional[str] = None

    # Purpose / RmtInf
    purpose_code: Optional[str] = None
    category_purpose: Optional[str] = None
    remittance_info: Optional[str] = None  # Ustrd simple form

    # UETR (wenn leer: Pipeline generiert automatisch UUIDv4)
    uetr: Optional[str] = None

    # Negative Testing
    violate_rule: Optional[str] = None

    # Freitext-Overrides (Dot-Notation)
    overrides: Dict[str, str] = {}

    # Meta
    expected_api_response: Optional[str] = None
    remarks: Optional[str] = None


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

class Pacs008TestCaseResult(BaseModel):
    """Ergebnis eines pacs.008-Testcases aus der Pipeline."""

    testcase_id: str
    titel: str
    flavor: Pacs008Flavor
    expected_result: ExpectedResult

    xsd_valid: bool
    xsd_errors: List[str] = []

    business_rule_results: List["BusinessRuleResultLite"] = []

    finaplo_valid: Optional[bool] = None  # None = FINaplo nicht aufgerufen
    finaplo_errors: List[str] = []

    overall_pass: bool
    xml_file_path: Optional[str] = None
    remarks: Optional[str] = None


class BusinessRuleResultLite(BaseModel):
    """Einfaches Rule-Result-Objekt fuer den pacs.008-Report.

    Parallel zu ``ValidationResult`` aus pain.001, aber lokal gehalten,
    um Cycle-Imports zwischen ``business_rules.py`` und diesem Modul
    zu vermeiden.
    """

    rule_id: str
    rule_description: str
    passed: bool
    details: Optional[str] = None


# Forward-ref cleanup
Pacs008TestCaseResult.model_rebuild()
