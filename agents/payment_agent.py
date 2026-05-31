import json
import uuid
from datetime import datetime
from pathlib import Path

from models.schemas import (
    ApprovalDecision,
    ExtractedInvoice,
    PaymentResult,
)
from database.queries import save_processed_invoice, save_rejected_invoice
from utils.logger import log_invoice_run


# ─── Mock Payment API ─────────────────────────────────────────────────────────

def mock_payment(vendor: str, amount: float, currency: str = "USD") -> dict:
    """
    Mock payment API — simulates sending payment.
    In production this would call a real banking API.
    """
    transaction_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    print(f"  💳 Payment sent: {currency} {amount:,.2f} → {vendor}")
    print(f"  Transaction ID: {transaction_id}")
    return {
        "status": "success",
        "transaction_id": transaction_id,
        "vendor": vendor,
        "amount": amount,
        "currency": currency,
        "processed_at": datetime.now().isoformat()
    }


# ─── Main Payment Logic ───────────────────────────────────────────────────────

def process_payment(
    invoice: ExtractedInvoice,
    decision: ApprovalDecision,
) -> PaymentResult:
    """
    Execute payment or log rejection based on approval decision.
    Always writes to audit trail.
    """
    if decision.decision == "approve":
        # Call mock payment API
        result = mock_payment(
            vendor=invoice.vendor,
            amount=invoice.stated_total,
            currency=invoice.currency
        )

        # Save to DB audit trail
        save_processed_invoice(
            invoice_number=invoice.invoice_number,
            vendor=invoice.vendor,
            total_amount=invoice.stated_total,
            currency=invoice.currency,
            decision="approved",
            risk_score=decision.risk_score,
            fraud_signals=json.dumps(decision.flags_considered),
            processing_time_ms=0,
            llm_cost_usd=0.0
        )

        return PaymentResult(
            status="paid",
            vendor=invoice.vendor,
            amount=invoice.stated_total,
            currency=invoice.currency,
            invoice_number=invoice.invoice_number,
            transaction_id=result["transaction_id"],
            processed_at=datetime.now().isoformat()
        )

    elif decision.decision == "flag_for_review":
        # Save as flagged — needs human review
        save_processed_invoice(
            invoice_number=invoice.invoice_number,
            vendor=invoice.vendor,
            total_amount=invoice.stated_total,
            currency=invoice.currency,
            decision="flagged",
            risk_score=decision.risk_score,
            fraud_signals=json.dumps(decision.flags_considered),
            processing_time_ms=0,
            llm_cost_usd=0.0
        )

        return PaymentResult(
            status="flagged",
            vendor=invoice.vendor,
            amount=invoice.stated_total,
            currency=invoice.currency,
            invoice_number=invoice.invoice_number,
            rejection_reason=f"Flagged for human review: {decision.reasoning}",
            processed_at=datetime.now().isoformat()
        )

    else:
        # Rejected — log with full reasoning
        save_rejected_invoice(
            invoice_number=invoice.invoice_number,
            reason=decision.reasoning,
            flags=json.dumps(decision.flags_considered)
        )

        save_processed_invoice(
            invoice_number=invoice.invoice_number,
            vendor=invoice.vendor,
            total_amount=invoice.stated_total,
            currency=invoice.currency,
            decision="rejected",
            risk_score=decision.risk_score,
            fraud_signals=json.dumps(decision.flags_considered),
            processing_time_ms=0,
            llm_cost_usd=0.0
        )

        return PaymentResult(
            status="rejected",
            vendor=invoice.vendor,
            amount=invoice.stated_total,
            currency=invoice.currency,
            invoice_number=invoice.invoice_number,
            rejection_reason=decision.reasoning,
            processed_at=datetime.now().isoformat()
        )


# ─── LangGraph Node ───────────────────────────────────────────────────────────

def payment_node(state: dict) -> dict:
    """
    LangGraph node for payment processing.
    Final node in the pipeline.
    """
    extracted = state.get("extracted_invoice")
    decision = state.get("approval_decision")

    if not extracted or not decision:
        return {
            "payment_result": None,
            "error": "Missing invoice or approval decision"
        }

    try:
        result = process_payment(extracted, decision)

        # Write full audit log
        log_invoice_run(
            invoice_number=extracted.invoice_number,
            invoice_path=state.get("invoice_path", ""),
            extracted=extracted.model_dump(),
            validation=state.get("validation_result").model_dump()
                if state.get("validation_result") else {},
            approval=decision.model_dump(),
            payment=result.model_dump(),
            processing_time_ms=0,
            llm_cost_usd=state.get("llm_cost_usd", 0.0)
        )

        return {"payment_result": result}

    except Exception as e:
        return {
            "payment_result": None,
            "error": f"Payment processing failed: {e}"
        }