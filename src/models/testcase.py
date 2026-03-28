from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PaymentType(str, Enum):
    SEPA = "SEPA"
    DOMESTIC_QR = "Domestic-QR"
    DOMESTIC_IBAN = "Domestic-IBAN"
    CBPR_PLUS = "CBPR+"


class Standard(str, Enum):
    SPS_2025 = "sps2025"
    CBPR_PLUS_2026 = "cbpr+2026"


class ExpectedResult(str, Enum):
    OK = "OK"
    NOK = "NOK"


class DebtorInfo(BaseModel):
    """Debtor-Daten. Nur IBAN ist Pflicht, Rest wird generiert."""

    name: Optional[str] = None
    iban: str
    bic: Optional[str] = None
    street: Optional[str] = None
    building: Optional[str] = None
    postal_code: Optional[str] = None
    town: Optional[str] = None
    country: str = "CH"


class TransactionInput(BaseModel):
    """Pro-Transaktions-Daten aus dem Excel (eine Zeile)."""

    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    creditor_name: Optional[str] = None
    creditor_iban: Optional[str] = None
    creditor_bic: Optional[str] = None
    creditor_address: Optional[str] = None
    remittance_info: Optional[str] = None
    overrides: Dict[str, str] = {}


class TestCase(BaseModel):
    testcase_id: str
    titel: str
    ziel: str
    expected_result: ExpectedResult
    payment_type: Optional[PaymentType] = None
    amount: Optional[Decimal] = Field(None, decimal_places=2)
    currency: Optional[str] = None
    debtor: DebtorInfo
    overrides: Dict[str, str] = {}
    violate_rule: Optional[str] = None
    tx_count: int = 1
    transaction_inputs: List[TransactionInput] = []
    standard: Standard = Standard.SPS_2025
    group_id: Optional[str] = None
    expected_api_response: Optional[str] = None
    remarks: Optional[str] = None


class Transaction(BaseModel):
    end_to_end_id: str
    uetr: Optional[str] = None
    amount: Decimal = Field(..., decimal_places=2)
    currency: str
    creditor_name: str
    creditor_iban: str
    creditor_address: Optional[Dict[str, str]] = None
    creditor_bic: Optional[str] = None
    charge_bearer: Optional[str] = None
    remittance_info: Optional[Dict[str, str]] = None
    overrides: Dict[str, str] = {}


class PaymentInstruction(BaseModel):
    msg_id: str
    pmt_inf_id: str
    pmt_mtd: str = "TRF"
    cre_dt_tm: str
    reqd_exctn_dt: str
    debtor: DebtorInfo
    service_level: Optional[str] = None
    local_instrument: Optional[str] = None
    category_purpose: Optional[str] = None
    charge_bearer: Optional[str] = None
    transactions: List[Transaction]


class Pain001Document(BaseModel):
    """Repräsentiert ein komplettes pain.001 XML-Dokument mit 1..n PmtInf-Blöcken."""

    msg_id: str
    cre_dt_tm: str
    initiating_party_name: str
    payment_instructions: List[PaymentInstruction]


class ValidationResult(BaseModel):
    rule_id: str
    rule_description: str
    passed: bool
    details: Optional[str] = None


class TestCaseResult(BaseModel):
    testcase_id: str
    titel: str
    payment_type: PaymentType
    expected_result: ExpectedResult
    xsd_valid: bool
    xsd_errors: List[str] = []
    business_rule_results: List[ValidationResult] = []
    overall_pass: bool
    xml_file_path: Optional[str] = None
    remarks: Optional[str] = None
