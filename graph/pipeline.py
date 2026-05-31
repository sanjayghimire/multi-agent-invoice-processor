import time
from typing import Any
from langgraph.graph import StateGraph, END
from models.schemas import InvoiceState
from agents.ingestion_agent import ingestion_node
from agents.validation_agent import validation_node
from agents.approval_agent import approval_node
from agents.payment_agent import payment_node


# â”€â”€â”€ Routing Functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def route_after_ingestion(state: dict) -> str:
    """
    After ingestion â€” check if extraction succeeded.
    """
    if state.get("error") or not state.get("extracted_invoice"):
        return "payment"  # Skip to payment which logs the error
    return "validation"


def route_after_validation(state: dict) -> str:
    """
    After validation â€” all invoices go to approval.
    Approval agent handles both clean and flagged invoices.
    """
    if state.get("error"):
        return "payment"
    return "approval"


def route_after_approval(state: dict) -> str:
    """
    After approval â€” always go to payment.
    Payment agent handles approve/reject/flag cases.
    """
    return "payment"


# â”€â”€â”€ State Adapter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def make_state_dict(invoice_path: str) -> dict:
    """Create initial state dict for a pipeline run."""
    return {
        "invoice_path": invoice_path,
        "invoice_number": None,
        "extracted_invoice": None,
        "validation_result": None,
        "approval_decision": None,
        "payment_result": None,
        "error": None,
        "processing_start": time.time(),
        "llm_tokens_used": 0,
        "llm_cost_usd": 0.0
    }


# ─── Node Wrappers (ensure state merging works correctly) ────────────────────

def ingestion_node_wrapped(state: dict) -> dict:
    result = ingestion_node(state)
    return {**state, **result}


def validation_node_wrapped(state: dict) -> dict:
    result = validation_node(state)
    return {**state, **result}


def approval_node_wrapped(state: dict) -> dict:
    result = approval_node(state)
    return {**state, **result}


def payment_node_wrapped(state: dict) -> dict:
    result = payment_node(state)
    return {**state, **result}


# ─── Build Graph ──────────────────────────────────────────────────────────────

def build_pipeline():
    """
    Build and compile the LangGraph pipeline.
    Returns compiled graph ready to invoke.
    """
    graph = StateGraph(dict)

    # Use wrapped nodes that preserve full state
    graph.add_node("ingestion", ingestion_node_wrapped)
    graph.add_node("validation", validation_node_wrapped)
    graph.add_node("approval", approval_node_wrapped)
    graph.add_node("payment", payment_node_wrapped)

    graph.set_entry_point("ingestion")

    graph.add_conditional_edges(
        "ingestion",
        route_after_ingestion,
        {
            "validation": "validation",
            "payment": "payment"
        }
    )

    graph.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "approval": "approval",
            "payment": "payment"
        }
    )

    graph.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "payment": "payment"
        }
    )

    graph.add_edge("payment", END)

    return graph.compile()

# â”€â”€â”€ Run Single Invoice â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def run_invoice(invoice_path: str, verbose: bool = True) -> dict:
    """
    Run a single invoice through the full pipeline.
    Returns final state dict.
    """
    pipeline = build_pipeline()
    state = make_state_dict(invoice_path)

    start_time = time.time()

    if verbose:
        print(f"\n{'='*60}")
        print(f"Processing: {invoice_path}")
        print(f"{'='*60}")

    # Run the pipeline
    final_state = pipeline.invoke(state)

    elapsed = round((time.time() - start_time) * 1000)

    if verbose:
        _print_result(final_state, elapsed)

    return final_state


# â”€â”€â”€ Run Batch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def run_batch(invoice_paths: list[str], verbose: bool = True) -> list[dict]:
    """
    Run multiple invoices through the pipeline.
    Returns list of final states.
    """
    results = []
    pipeline = build_pipeline()

    print(f"\nProcessing {len(invoice_paths)} invoices...")
    print("=" * 60)

    for i, path in enumerate(invoice_paths, 1):
        print(f"\n[{i}/{len(invoice_paths)}] {path}")
        state = make_state_dict(path)

        try:
            final_state = pipeline.invoke(state)
            results.append(final_state)
            if verbose:
                _print_result(final_state, 0)
        except Exception as e:
            print(f"  Pipeline error: {e}")
            results.append({**state, "error": str(e)})

    _print_batch_summary(results)
    return results


# â”€â”€â”€ Pretty Printing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _print_result(state: dict, elapsed_ms: int) -> None:
    """Print a formatted result for one invoice."""
    extracted = state.get("extracted_invoice")
    validation = state.get("validation_result")
    approval = state.get("approval_decision")
    payment = state.get("payment_result")
    error = state.get("error")

    if error and not payment:
        print(f"  ERROR   : {error}")
        return

    if extracted:
        print(f"  Vendor  : {extracted.vendor}")
        print(f"  Amount  : ${extracted.stated_total:,.2f} {extracted.currency}")
        print(f"  Items   : {len(extracted.items)} line item(s)")

    if validation:
        stock_ok = all(s.is_sufficient for s in validation.stock_checks)
        print(f"  Stock   : {'OK' if stock_ok else 'Issues'}")
        print(f"  Math    : {'Verified' if validation.math_verified else 'Mismatch'}")
        print(f"  Fraud   : {validation.fraud_score:.2f}/1.00")

    if approval:
        print(f"  Decision: {approval.decision.upper()}")
        print(f"  Reason  : {approval.reasoning[:100]}...")

    if payment:
        if payment.status == "paid":
            print(f"  Payment : PAID (TXN: {payment.transaction_id})")
        elif payment.status == "flagged":
            print(f"  Payment : FLAGGED FOR REVIEW")
        else:
            print(f"  Payment : REJECTED")

    cost = state.get("llm_cost_usd", 0.0)
    print(f"  LLM Cost: ${cost:.4f}")


def _print_batch_summary(results: list[dict]) -> None:
    """Print summary statistics for a batch run."""
    total = len(results)
    approved = sum(
        1 for r in results
        if r.get("payment_result") and
        r["payment_result"].status == "paid"
    )
    rejected = sum(
        1 for r in results
        if r.get("payment_result") and
        r["payment_result"].status == "rejected"
    )
    flagged = sum(
        1 for r in results
        if r.get("payment_result") and
        r["payment_result"].status == "flagged"
    )
    errors = sum(1 for r in results if r.get("error") and
                 not r.get("payment_result"))

    approved_amount = sum(
        r["payment_result"].amount
        for r in results
        if r.get("payment_result") and
        r["payment_result"].status == "paid"
    )
    rejected_amount = sum(
        r["payment_result"].amount
        for r in results
        if r.get("payment_result") and
        r["payment_result"].status == "rejected"
    )
    total_cost = sum(r.get("llm_cost_usd", 0.0) for r in results)

    print(f"\n{'='*60}")
    print(f"BATCH SUMMARY")
    print(f"{'='*60}")
    print(f"  Total processed  : {total}")
    print(f"  Approved         : {approved}  (${approved_amount:,.2f} cleared)")
    print(f"  Rejected         : {rejected}  (${rejected_amount:,.2f} blocked)")
    print(f"  Flagged          : {flagged}")
    print(f"  Errors           : {errors}")
    print(f"  Total LLM cost   : ${total_cost:.4f}")
    print(f"  Cost/invoice     : ${total_cost/total:.4f}" if total > 0 else "")

    # Business impact
    manual_cost = total * 4 * 25  # 4hrs Ã— $25/hr per invoice
    if total_cost > 0:
        roi = int(manual_cost / total_cost)
        print(f"\n  Business Impact:")
        print(f"  Manual processing cost : ${manual_cost:,.2f}")
        print(f"  AI processing cost     : ${total_cost:.4f}")
        print(f"  ROI                    : {roi:,}x")
    print(f"{'='*60}")
