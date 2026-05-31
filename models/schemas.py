from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
from datetime import datetime


# ─── LINE ITEM ────────────────────────────────────────────────────────────────

class LineItem(BaseModel):
    item_name: str
    quantity: float
    unit_price: float
    total: float
    notes: Optional[str] = None

    @field_validator("item_name")
    @classmethod
    def normalize_item_name(cls, v: str) -> str:
        """Widget A → WidgetA, Gadget X → GadgetX"""
        return v.replace(" ", "").strip()

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"Quantity must be positive, got {v}")
        return v


# ─── EXTRACTED INVOICE ────────────────────────────────────────────────────────

class ExtractedInvoice(BaseModel):
    invoice_number: str
    vendor: str
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    items: List[LineItem]
    stated_total: float
    currency: str = "USD"
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    extraction_warnings: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None


# ─── STOCK CHECK ──────────────────────────────────────────────────────────────

class StockCheck(BaseModel):
    item_name: str
    requested_qty: float
    available_stock: int
    is_sufficient: bool
    shortfall: float = 0.0


# ─── VALIDATION RESULT ────────────────────────────────────────────────────────

class ValidationResult(BaseModel):
    is_valid: bool
    stock_checks: List[StockCheck] = Field(default_factory=list)
    unknown_items: List[str] = Field(default_factory=list)
    math_verified: bool = True
    computed_total: float = 0.0
    stated_total: float = 0.0
    total_discrepancy: float = 0.0
    fraud_signals: List[str] = Field(default_factory=list)
    fraud_score: float = Field(default=0.0, ge=0.0, le=1.0)
    currency_mismatch: bool = False
    flags: List[str] = Field(default_factory=list)
    is_duplicate: bool = False


# ─── APPROVAL DECISION ────────────────────────────────────────────────────────

class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject", "flag_for_review"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    risk_score: float = Field(ge=0.0, le=1.0)
    critique_rounds: int = 0
    flags_considered: List[str] = Field(default_factory=list)
    requires_vp_review: bool = False


# ─── PAYMENT RESULT ───────────────────────────────────────────────────────────

class PaymentResult(BaseModel):
    status: Literal["paid", "rejected", "flagged"]
    vendor: str
    amount: float
    currency: str = "USD"
    invoice_number: str
    transaction_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    processed_at: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )


# ─── PIPELINE STATE ───────────────────────────────────────────────────────────
# This is the shared whiteboard passed between all agents in LangGraph

class InvoiceState(BaseModel):
    # Input
    invoice_path: str
    invoice_number: Optional[str] = None

    # Agent outputs (filled in as pipeline runs)
    extracted_invoice: Optional[ExtractedInvoice] = None
    validation_result: Optional[ValidationResult] = None
    approval_decision: Optional[ApprovalDecision] = None
    payment_result: Optional[PaymentResult] = None

    # Metadata
    error: Optional[str] = None
    processing_start: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    llm_tokens_used: int = 0
    llm_cost_usd: float = 0.0


# ─── BATCH SUMMARY ────────────────────────────────────────────────────────────

class BatchSummary(BaseModel):
    total_invoices: int = 0
    approved: int = 0
    rejected: int = 0
    flagged: int = 0
    total_approved_amount: float = 0.0
    total_rejected_amount: float = 0.0
    total_llm_cost_usd: float = 0.0
    errors: int = 0
    processing_time_seconds: float = 0.0