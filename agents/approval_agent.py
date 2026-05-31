import json
import os
import re

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from models.schemas import (
    ApprovalDecision,
    ExtractedInvoice,
    ValidationResult,
)
from utils.cost_tracker import calculate_cost

load_dotenv()


# ─── LLM Factory ──────────────────────────────────────────────────────────────

def get_reasoning_llm():
    """Return the configured LLM for reasoning tasks."""
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    model = os.getenv("REASONING_MODEL", "claude-sonnet-4-5")

    if provider == "anthropic":
        return ChatAnthropic(
            model=model,
            temperature=0,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    elif provider == "openai":
        return ChatOpenAI(
            model=model,
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY")
        )
    elif provider == "grok":
        return ChatOpenAI(
            model=model,
            temperature=0,
            base_url="https://api.x.ai/v1",
            api_key=os.getenv("XAI_API_KEY")
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


# ─── Rule-Based Pre-checks ────────────────────────────────────────────────────

def apply_hard_rules(
    invoice: ExtractedInvoice,
    validation: ValidationResult,
) -> tuple[str | None, list[str]]:
    """
    Apply deterministic rules before LLM reasoning.
    Returns (forced_decision, flags).
    forced_decision is None if LLM should decide.
    """
    flags = []

    # Auto-reject: fraud score too high
    if validation.fraud_score >= 0.75:
        flags.append(f"Auto-reject: fraud score {validation.fraud_score}")
        return "reject", flags

    # Auto-reject: negative total
    if invoice.stated_total < 0:
        flags.append("Auto-reject: negative total amount")
        return "reject", flags

    # Auto-reject: no line items
    if not invoice.items:
        flags.append("Auto-reject: no line items found")
        return "reject", flags

    # Auto-reject: missing vendor
    if not invoice.vendor or invoice.vendor == "Unknown":
        flags.append("Auto-reject: missing vendor")
        return "reject", flags

    # Flag for review: currency mismatch
    if validation.currency_mismatch:
        flags.append(f"Flag: non-USD currency {invoice.currency}")
        return "flag_for_review", flags

    # Requires VP review: over $10K
    if invoice.stated_total > 10000:
        flags.append(f"VP review required: amount ${invoice.stated_total:,.2f} > $10,000")

    return None, flags


# ─── LLM Decision ─────────────────────────────────────────────────────────────

def llm_decide(
    invoice: ExtractedInvoice,
    validation: ValidationResult,
    flags: list[str],
) -> tuple[dict, int]:
    """
    Use LLM to make approval decision.
    Returns (decision_dict, output_tokens).
    """
    llm = get_reasoning_llm()

    # Build context summary
    stock_summary = []
    for check in validation.stock_checks:
        status = "✓" if check.is_sufficient else "✗"
        stock_summary.append(
            f"  {status} {check.item_name}: "
            f"requested {check.requested_qty}, "
            f"available {check.available_stock}"
        )

    context = f"""
INVOICE DETAILS:
  Invoice Number : {invoice.invoice_number}
  Vendor         : {invoice.vendor}
  Amount         : ${invoice.stated_total:,.2f} {invoice.currency}
  Due Date       : {invoice.due_date or 'NOT PROVIDED'}
  Payment Terms  : {invoice.payment_terms or 'NOT PROVIDED'}
  Notes          : {invoice.notes or 'None'}

LINE ITEMS:
{chr(10).join(f"  - {i.item_name}: qty {i.quantity} @ ${i.unit_price:.2f}" for i in invoice.items)}

VALIDATION RESULTS:
  Stock checks:
{chr(10).join(stock_summary)}
  Unknown items  : {validation.unknown_items or 'None'}
  Math verified  : {validation.math_verified}
  Discrepancy    : ${validation.total_discrepancy:.2f}
  Fraud score    : {validation.fraud_score:.2f} / 1.00
  Fraud signals  : {validation.fraud_signals or 'None'}
  Flags          : {flags or 'None'}
  Currency OK    : {not validation.currency_mismatch}

EXTRACTION WARNINGS:
  {invoice.extraction_warnings or 'None'}
"""

    system_prompt = """You are a senior VP of Finance at Acme Corp reviewing invoices.
Your job is to make approval decisions based on all available evidence.

Rules you must follow:
- Invoices with stock shortfalls must be REJECTED
- Invoices with unknown items must be REJECTED
- Invoices with math discrepancies > $1.00 must be REJECTED
- Invoices over $10,000 require extra scrutiny
- Fraud signals significantly increase rejection likelihood
- Missing vendor or unparseable dates increase risk

Return ONLY a valid JSON object:
{
  "decision": "approve" | "reject" | "flag_for_review",
  "confidence": 0.0 to 1.0,
  "reasoning": "detailed explanation of decision",
  "risk_score": 0.0 to 1.0,
  "requires_vp_review": true | false,
  "flags_considered": ["list", "of", "key", "factors"]
}"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Review this invoice and make a decision:\n{context}")
    ])

    content = response.content.strip()
    content = re.sub(r'^```json\s*', '', content)
    content = re.sub(r'^```\s*', '', content)
    content = re.sub(r'\s*```$', '', content)

    decision_data = json.loads(content)

    # Safety check: force reject if reasoning contains stock shortfall language
    reasoning_lower = decision_data.get("reasoning", "").lower()

    strong_reject_words = [
        "must be rejected",
        "should be rejected",
        "cannot be approved",
        "critical stock shortfall",
        "stock shortfall",
        "exceeds available",
        "insufficient stock"
    ]

    reasoning_says_reject = any(w in reasoning_lower for w in strong_reject_words)

    if reasoning_says_reject and decision_data.get("decision") in ["approve", "flag_for_review"]:
        decision_data["decision"] = "reject"
        decision_data["reasoning"] = (
            "[Auto-corrected: stock shortfall detected in reasoning] "
            + decision_data["reasoning"]
        )

    output_tokens = len(content.split()) * 2
    return decision_data, output_tokens


# ─── Critique Loop ────────────────────────────────────────────────────────────

def critique_decision(
    decision_data: dict,
    invoice: ExtractedInvoice,
    validation: ValidationResult,
) -> tuple[dict, bool]:
    """
    Critic agent reviews the initial decision.
    Returns (critique_result, needs_revision).
    """
    llm = get_reasoning_llm()

    critique_prompt = f"""You are a risk management auditor reviewing an approval decision.

ORIGINAL DECISION: {decision_data['decision'].upper()}
REASONING: {decision_data['reasoning']}
RISK SCORE: {decision_data['risk_score']}

INVOICE FACTS:
- Vendor: {invoice.vendor}
- Amount: ${invoice.stated_total:,.2f}
- Fraud score: {validation.fraud_score}
- Stock failures: {[s.item_name for s in validation.stock_checks if not s.is_sufficient]}
- Unknown items: {validation.unknown_items}
- Math verified: {validation.math_verified}
- Fraud signals: {validation.fraud_signals}

Critically evaluate this decision:
1. Are there any fraud signals that were not adequately considered?
2. Is the risk score appropriate given the evidence?
3. Would you change the decision?

Return ONLY a valid JSON object:
{{
  "agrees": true | false,
  "critique": "your analysis",
  "recommended_decision": "approve" | "reject" | "flag_for_review",
  "recommended_risk_score": 0.0 to 1.0
}}"""

    response = llm.invoke([
        HumanMessage(content=critique_prompt)
    ])

    content = response.content.strip()
    content = re.sub(r'^```json\s*', '', content)
    content = re.sub(r'^```\s*', '', content)
    content = re.sub(r'\s*```$', '', content)

    critique = json.loads(content)
    needs_revision = not critique.get("agrees", True)
    return critique, needs_revision


# ─── Main Approval Logic ──────────────────────────────────────────────────────

def approve_invoice(
    invoice: ExtractedInvoice,
    validation: ValidationResult,
) -> tuple[ApprovalDecision, float]:
    """
    Main approval function with critique loop.
    Returns (ApprovalDecision, llm_cost_usd).
    """
    model = os.getenv("REASONING_MODEL", "claude-sonnet-4-5")
    total_cost = 0.0
    critique_rounds = 0

    # Step 1: Apply hard rules first
    forced_decision, flags = apply_hard_rules(invoice, validation)

    if forced_decision:
        # No LLM needed — hard rule triggered
        risk_score = validation.fraud_score
        reasoning = f"Auto-decision by rule: {'; '.join(flags)}"

        return ApprovalDecision(
            decision=forced_decision,
            confidence=0.95,
            reasoning=reasoning,
            risk_score=risk_score,
            critique_rounds=0,
            flags_considered=flags,
            requires_vp_review=invoice.stated_total > 10000
        ), 0.0

    # Step 2: LLM makes initial decision
    decision_data, output_tokens = llm_decide(invoice, validation, flags)
    input_tokens = 800
    total_cost += calculate_cost(model, input_tokens, output_tokens)

    # Step 3: Critique loop (max 2 rounds)
    max_rounds = 2
    while critique_rounds < max_rounds:
        critique, needs_revision = critique_decision(
            decision_data, invoice, validation
        )
        total_cost += calculate_cost(model, 600, 200)
        critique_rounds += 1

        if not needs_revision:
            # Critic agrees — we're done
            break

        # Critic disagrees — update decision
        decision_data["decision"] = critique["recommended_decision"]
        decision_data["risk_score"] = critique["recommended_risk_score"]
        decision_data["reasoning"] = (
            f"{decision_data['reasoning']} "
            f"[Revised after critique: {critique['critique']}]"
        )

    # Add VP review flag if needed
    requires_vp = (
        invoice.stated_total > 10000 or
        decision_data.get("requires_vp_review", False)
    )

    all_flags = flags + decision_data.get("flags_considered", [])

    return ApprovalDecision(
        decision=decision_data["decision"],
        confidence=float(decision_data.get("confidence", 0.8)),
        reasoning=decision_data["reasoning"],
        risk_score=float(decision_data.get("risk_score", 0.5)),
        critique_rounds=critique_rounds,
        flags_considered=list(set(all_flags)),
        requires_vp_review=requires_vp
    ), total_cost


# ─── LangGraph Node ───────────────────────────────────────────────────────────

def approval_node(state: dict) -> dict:
    """
    LangGraph node for invoice approval.
    """
    extracted = state.get("extracted_invoice")
    validation = state.get("validation_result")

    if not extracted or not validation:
        return {
            "approval_decision": None,
            "error": "Missing extracted invoice or validation result"
        }

    try:
        decision, llm_cost = approve_invoice(extracted, validation)
        return {
            "approval_decision": decision,
            "llm_cost_usd": state.get("llm_cost_usd", 0.0) + llm_cost
        }
    except Exception as e:
        return {
            "approval_decision": None,
            "error": f"Approval failed: {e}"
        }
