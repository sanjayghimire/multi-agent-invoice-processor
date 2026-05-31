import streamlit as st
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Acme Invoice Processor",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    .stApp {
        background-color: #0a0e1a;
        color: #e2e8f0;
    }

    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
        border: 1px solid #1e40af;
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }

    .main-header::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, #1d4ed8, #3b82f6, #60a5fa, #3b82f6, #1d4ed8);
    }

    .main-title {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 2rem;
        font-weight: 600;
        color: #60a5fa;
        letter-spacing: -0.02em;
        margin: 0;
    }

    .main-subtitle {
        color: #94a3b8;
        font-size: 0.9rem;
        margin-top: 0.25rem;
        font-family: 'IBM Plex Mono', monospace;
    }

    .metric-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 1.25rem;
        text-align: center;
        transition: border-color 0.2s;
    }

    .metric-card:hover { border-color: #3b82f6; }

    .metric-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 2rem;
        font-weight: 600;
        line-height: 1;
    }

    .metric-label {
        font-size: 0.75rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 0.4rem;
    }

    .invoice-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.6rem;
        border-left: 4px solid #1e293b;
        transition: all 0.2s;
    }

    .invoice-card:hover { border-color: #3b82f6; background: #141e30; }
    .invoice-card.approved { border-left-color: #22c55e; }
    .invoice-card.rejected { border-left-color: #ef4444; }
    .invoice-card.flagged  { border-left-color: #f59e0b; }
    .invoice-card.error    { border-left-color: #6b7280; }

    .invoice-number {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem;
        color: #60a5fa;
        font-weight: 600;
    }

    .invoice-vendor {
        font-size: 0.95rem;
        font-weight: 600;
        color: #e2e8f0;
    }

    .invoice-amount {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1rem;
        color: #94a3b8;
    }

    .badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-family: 'IBM Plex Mono', monospace;
    }

    .badge-approve { background: #14532d; color: #4ade80; border: 1px solid #166534; }
    .badge-reject  { background: #450a0a; color: #f87171; border: 1px solid #7f1d1d; }
    .badge-flag    { background: #451a03; color: #fbbf24; border: 1px solid #78350f; }
    .badge-error   { background: #1c1c1c; color: #9ca3af; border: 1px solid #374151; }

    .reasoning-box {
        background: #080d18;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-size: 0.82rem;
        color: #94a3b8;
        font-family: 'IBM Plex Mono', monospace;
        line-height: 1.5;
        margin-top: 0.5rem;
    }

    .fraud-bar-container {
        background: #1e293b;
        border-radius: 4px;
        height: 6px;
        margin-top: 4px;
        overflow: hidden;
    }

    .stButton > button {
        background: linear-gradient(135deg, #1d4ed8, #2563eb);
        color: white;
        border: none;
        border-radius: 8px;
        font-family: 'IBM Plex Mono', monospace;
        font-weight: 600;
        letter-spacing: 0.05em;
        padding: 0.6rem 1.5rem;
        transition: all 0.2s;
        width: 100%;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb, #3b82f6);
        transform: translateY(-1px);
    }

    .stProgress > div > div {
        background: linear-gradient(90deg, #1d4ed8, #3b82f6) !important;
    }

    .roi-highlight {
        background: linear-gradient(135deg, #0c1a3a, #0f2a5a);
        border: 1px solid #1d4ed8;
        border-radius: 10px;
        padding: 1rem 1.5rem;
        text-align: center;
    }

    .sidebar-section {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    .agent-step {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.4rem 0;
        font-size: 0.82rem;
        font-family: 'IBM Plex Mono', monospace;
        color: #64748b;
    }

    .agent-step.active { color: #60a5fa; }
    .agent-step.done   { color: #4ade80; }

    div[data-testid="stSidebar"] {
        background-color: #060a14;
        border-right: 1px solid #1e293b;
    }

    .stSelectbox > div, .stFileUploader > div {
        background: #0f172a !important;
        border-color: #1e293b !important;
    }

    hr { border-color: #1e293b; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def decision_badge(decision: str) -> str:
    icons = {"approve": "✓ APPROVED", "reject": "✗ REJECTED",
             "flag_for_review": "⚠ FLAGGED", "error": "! ERROR"}
    cls = {"approve": "approve", "reject": "reject",
           "flag_for_review": "flag", "error": "error"}
    label = icons.get(decision, decision.upper())
    c = cls.get(decision, "error")
    return f'<span class="badge badge-{c}">{label}</span>'


def fraud_bar(score: float) -> str:
    color = "#4ade80" if score < 0.3 else "#fbbf24" if score < 0.6 else "#ef4444"
    pct = int(score * 100)
    return f"""
    <div style="font-size:0.75rem;color:#64748b;font-family:'IBM Plex Mono',monospace;">
        FRAUD SCORE: {score:.2f}
        <div class="fraud-bar-container">
            <div style="width:{pct}%;height:100%;background:{color};border-radius:4px;"></div>
        </div>
    </div>"""


def format_amount(amount: float, currency: str = "USD") -> str:
    symbol = "€" if currency == "EUR" else "$"
    return f"{symbol}{amount:,.2f} {currency}"


def run_single_invoice(path: str) -> dict:
    """Run pipeline on a single invoice file."""
    from graph.pipeline import run_invoice
    return run_invoice(str(path), verbose=False)


def run_batch_invoices(paths: list) -> list:
    """Run pipeline on multiple invoice files."""
    from graph.pipeline import build_pipeline, make_state_dict
    pipeline = build_pipeline()
    results = []
    for path in paths:
        state = make_state_dict(str(path))
        try:
            final = pipeline.invoke(state)
            results.append(final)
        except Exception as e:
            results.append({**state, "error": str(e)})
    return results


def get_decision(state: dict) -> str:
    if state.get("error") and not state.get("payment_result"):
        return "error"
    pr = state.get("payment_result")
    if not pr:
        return "error"
    mapping = {"paid": "approve", "rejected": "reject", "flagged": "flag_for_review"}
    return mapping.get(pr.status, "error")


def render_invoice_card(state: dict, idx: int):
    """Render one invoice result as a styled card."""
    decision = get_decision(state)
    extracted = state.get("extracted_invoice")
    validation = state.get("validation_result")
    approval = state.get("approval_decision")
    payment = state.get("payment_result")

    inv_num = state.get("invoice_number", f"INV-{idx:04d}")
    vendor = extracted.vendor if extracted else "Unknown"
    amount = extracted.stated_total if extracted else 0
    currency = extracted.currency if extracted else "USD"
    fraud_score = validation.fraud_score if validation else 0.0
    reasoning = approval.reasoning[:200] + "..." if approval and len(approval.reasoning) > 200 else (approval.reasoning if approval else state.get("error", "No reasoning available"))
    cost = state.get("llm_cost_usd", 0.0)
    txn = payment.transaction_id if payment and hasattr(payment, "transaction_id") and payment.transaction_id else None

    card_class = {"approve": "approved", "reject": "rejected",
                  "flag_for_review": "flagged", "error": "error"}.get(decision, "error")

    with st.expander(f"{inv_num}  —  {vendor}  —  {format_amount(amount, currency)}", expanded=False):
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            st.markdown(f'<div class="invoice-number">{inv_num}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="invoice-vendor">{vendor}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="invoice-amount">{format_amount(amount, currency)}</div>', unsafe_allow_html=True)
            if txn:
                st.markdown(f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.72rem;color:#4ade80;margin-top:4px;">TXN: {txn}</div>', unsafe_allow_html=True)

        with col2:
            st.markdown(decision_badge(decision), unsafe_allow_html=True)
            st.markdown(fraud_bar(fraud_score), unsafe_allow_html=True)
            if validation:
                stock_ok = all(s.is_sufficient for s in validation.stock_checks)
                st.markdown(f'<div style="font-size:0.75rem;color:#64748b;font-family:IBM Plex Mono,monospace;margin-top:4px;">STOCK: {"OK" if stock_ok else "ISSUES"} &nbsp;|&nbsp; MATH: {"OK" if validation.math_verified else "MISMATCH"}</div>', unsafe_allow_html=True)

        with col3:
            st.markdown(f'<div style="text-align:right;font-family:IBM Plex Mono,monospace;font-size:0.75rem;color:#64748b;">LLM COST<br><span style="color:#94a3b8;font-size:1rem;">${cost:.4f}</span></div>', unsafe_allow_html=True)

        st.markdown(f'<div class="reasoning-box">{reasoning}</div>', unsafe_allow_html=True)

        # Flags
        if validation and validation.flags:
            st.markdown('<div style="margin-top:0.5rem;">' +
                "".join([f'<span style="background:#1e293b;color:#94a3b8;font-size:0.7rem;font-family:IBM Plex Mono,monospace;padding:2px 8px;border-radius:4px;margin-right:4px;margin-top:4px;display:inline-block;">{f}</span>' for f in validation.flags[:4]]) +
                '</div>', unsafe_allow_html=True)


# ── Main App ──────────────────────────────────────────────────────────────────

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <div class="main-title">ACME INVOICE PROCESSOR</div>
        <div class="main-subtitle">Multi-Agent AI Pipeline  //  LangGraph + Claude  //  Real-time Processing</div>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown('<div style="font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#3b82f6;letter-spacing:0.1em;margin-bottom:0.5rem;">PIPELINE STATUS</div>', unsafe_allow_html=True)

        st.markdown("""
        <div style="font-family:IBM Plex Mono,monospace;font-size:0.8rem;color:#4ade80;">
            ● INGESTION AGENT &nbsp; ready<br>
            ● VALIDATION AGENT &nbsp; ready<br>
            ● APPROVAL AGENT &nbsp; ready<br>
            ● PAYMENT AGENT &nbsp; ready
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        st.markdown('<div style="font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#3b82f6;letter-spacing:0.1em;margin-bottom:0.5rem;">CONFIGURATION</div>', unsafe_allow_html=True)

        provider = os.getenv("LLM_PROVIDER", "anthropic").upper()
        ext_model = os.getenv("EXTRACTION_MODEL", "claude-haiku-4-5")
        rea_model = os.getenv("REASONING_MODEL", "claude-sonnet-4-5")

        st.markdown(f"""
        <div style="font-family:IBM Plex Mono,monospace;font-size:0.75rem;color:#64748b;">
            PROVIDER: <span style="color:#94a3b8;">{provider}</span><br>
            EXTRACT:  <span style="color:#94a3b8;">{ext_model}</span><br>
            REASON:   <span style="color:#94a3b8;">{rea_model}</span>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Inventory
        st.markdown('<div style="font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#3b82f6;letter-spacing:0.1em;margin-bottom:0.5rem;">INVENTORY</div>', unsafe_allow_html=True)
        try:
            from database.queries import get_all_inventory
            inventory = get_all_inventory()
            for item in inventory:
                bar_pct = int((item["stock"] / 20) * 100)
                color = "#4ade80" if item["stock"] > 5 else "#f59e0b" if item["stock"] > 0 else "#ef4444"
                st.markdown(f"""
                <div style="margin-bottom:6px;">
                    <div style="display:flex;justify-content:space-between;font-family:IBM Plex Mono,monospace;font-size:0.72rem;">
                        <span style="color:#94a3b8;">{item['item']}</span>
                        <span style="color:{color};">{item['stock']} units</span>
                    </div>
                    <div style="background:#1e293b;border-radius:3px;height:4px;margin-top:2px;">
                        <div style="width:{min(bar_pct,100)}%;height:100%;background:{color};border-radius:3px;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            st.markdown(f'<div style="color:#ef4444;font-size:0.75rem;">DB Error: {e}</div>', unsafe_allow_html=True)

        st.divider()

        # Reset DB button
        if st.button("Reset Database"):
            try:
                from database.setup import reset_database
                reset_database()
                st.success("Database reset!")
                st.rerun()
            except Exception as e:
                st.error(f"Reset failed: {e}")

    # ── Main tabs ─────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["  SINGLE INVOICE  ", "  BATCH PROCESSING  ", "  AUDIT LOGS  "])

    # ── Tab 1: Single Invoice ─────────────────────────────────────────────────
    with tab1:
        st.markdown('<div style="font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#3b82f6;letter-spacing:0.1em;margin-bottom:1rem;">SELECT INVOICE</div>', unsafe_allow_html=True)

        invoice_dir = Path("data/invoices")
        if invoice_dir.exists():
            invoice_files = sorted([
                f for f in invoice_dir.iterdir()
                if f.suffix in [".txt", ".json", ".csv", ".xml", ".pdf"]
            ])
            file_names = [f.name for f in invoice_files]

            col1, col2 = st.columns([3, 1])
            with col1:
                selected = st.selectbox("Choose invoice file", file_names, label_visibility="collapsed")
            with col2:
                process_btn = st.button("PROCESS INVOICE")

            if selected and process_btn:
                selected_path = invoice_dir / selected
                with st.spinner(""):
                    # Show agent progress
                    progress_placeholder = st.empty()
                    steps = [
                        "Ingestion Agent — extracting data...",
                        "Validation Agent — checking stock & math...",
                        "Approval Agent — reasoning & critique...",
                        "Payment Agent — executing decision..."
                    ]
                    bar = st.progress(0)
                    for i, step in enumerate(steps):
                        progress_placeholder.markdown(f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.8rem;color:#60a5fa;">[ {step} ]</div>', unsafe_allow_html=True)
                        bar.progress((i + 1) * 25)
                        time.sleep(0.3)

                    result = run_single_invoice(str(selected_path))
                    progress_placeholder.empty()
                    bar.empty()

                st.markdown("---")
                st.markdown('<div style="font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#3b82f6;letter-spacing:0.1em;margin-bottom:0.5rem;">RESULT</div>', unsafe_allow_html=True)
                render_invoice_card(result, 1)

                # Store in session state
                if "single_results" not in st.session_state:
                    st.session_state.single_results = []
                st.session_state.single_results.append(result)

    # ── Tab 2: Batch Processing ───────────────────────────────────────────────
    with tab2:
        st.markdown('<div style="font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#3b82f6;letter-spacing:0.1em;margin-bottom:1rem;">BATCH PROCESSING</div>', unsafe_allow_html=True)

        invoice_dir = Path("data/invoices")
        if invoice_dir.exists():
            all_files = sorted([
                f for f in invoice_dir.iterdir()
                if f.suffix in [".txt", ".json", ".csv", ".xml", ".pdf"]
            ])

            # Filter duplicates
            from main import _filter_duplicates
            filtered = _filter_duplicates(all_files)

            st.markdown(f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.8rem;color:#94a3b8;">Found <span style="color:#60a5fa;">{len(all_files)}</span> files — processing <span style="color:#60a5fa;">{len(filtered)}</span> after deduplication</div>', unsafe_allow_html=True)
            st.markdown("")

            if st.button("RUN FULL BATCH"):
                results = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                results_container = st.container()

                for i, fpath in enumerate(filtered):
                    status_text.markdown(f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.8rem;color:#60a5fa;">Processing [{i+1}/{len(filtered)}]: {fpath.name}</div>', unsafe_allow_html=True)
                    progress_bar.progress((i + 1) / len(filtered))

                    result = run_single_invoice(str(fpath))
                    results.append(result)

                progress_bar.empty()
                status_text.empty()

                # Store results
                st.session_state.batch_results = results

                # Summary metrics
                st.markdown('<div style="font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#3b82f6;letter-spacing:0.1em;margin:1rem 0 0.5rem;">BATCH SUMMARY</div>', unsafe_allow_html=True)

                approved = [r for r in results if get_decision(r) == "approve"]
                rejected = [r for r in results if get_decision(r) == "reject"]
                flagged  = [r for r in results if get_decision(r) == "flag_for_review"]
                errors   = [r for r in results if get_decision(r) == "error"]

                approved_amt = sum(r["extracted_invoice"].stated_total for r in approved if r.get("extracted_invoice"))
                rejected_amt = sum(r["extracted_invoice"].stated_total for r in rejected if r.get("extracted_invoice"))
                total_cost   = sum(r.get("llm_cost_usd", 0) for r in results)

                c1, c2, c3, c4, c5 = st.columns(5)
                metrics = [
                    (c1, str(len(approved)), "APPROVED", "#4ade80"),
                    (c2, str(len(rejected)), "REJECTED", "#f87171"),
                    (c3, str(len(flagged)),  "FLAGGED",  "#fbbf24"),
                    (c4, f"${approved_amt:,.0f}", "CLEARED", "#60a5fa"),
                    (c5, f"${total_cost:.3f}", "LLM COST", "#a78bfa"),
                ]
                for col, val, label, color in metrics:
                    with col:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-value" style="color:{color};">{val}</div>
                            <div class="metric-label">{label}</div>
                        </div>
                        """, unsafe_allow_html=True)

                # ROI
                st.markdown("")
                manual_cost = len(results) * 4 * 25
                if total_cost > 0:
                    roi = int(manual_cost / total_cost)
                    st.markdown(f"""
                    <div class="roi-highlight">
                        <div style="font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#64748b;letter-spacing:0.1em;">BUSINESS IMPACT</div>
                        <div style="font-size:2rem;font-weight:700;color:#60a5fa;font-family:IBM Plex Mono,monospace;">{roi:,}x ROI</div>
                        <div style="font-size:0.8rem;color:#94a3b8;">Manual cost: ${manual_cost:,} &nbsp;|&nbsp; AI cost: ${total_cost:.4f} &nbsp;|&nbsp; Savings: ${manual_cost - total_cost:,.2f}</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Results list
                st.markdown('<div style="font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#3b82f6;letter-spacing:0.1em;margin:1rem 0 0.5rem;">INVOICE RESULTS</div>', unsafe_allow_html=True)
                for i, result in enumerate(results):
                    render_invoice_card(result, i + 1)

    # ── Tab 3: Audit Logs ─────────────────────────────────────────────────────
    with tab3:
        st.markdown('<div style="font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#3b82f6;letter-spacing:0.1em;margin-bottom:1rem;">AUDIT TRAIL</div>', unsafe_allow_html=True)

        logs_dir = Path("logs")
        if logs_dir.exists():
            log_files = sorted(logs_dir.glob("*.json"), reverse=True)

            if not log_files:
                st.markdown('<div style="font-family:IBM Plex Mono,monospace;font-size:0.8rem;color:#64748b;">No audit logs yet. Process some invoices first.</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.8rem;color:#94a3b8;">{len(log_files)} audit entries found</div>', unsafe_allow_html=True)
                st.markdown("")

                for log_file in log_files[:20]:
                    try:
                        with open(log_file) as f:
                            log_data = json.load(f)

                        inv_num = log_data.get("invoice_number", "UNKNOWN")
                        ts = log_data.get("timestamp", "")[:19].replace("T", " ")
                        cost = log_data.get("llm_cost_usd", 0)
                        decision = log_data.get("pipeline", {}).get("approval", {}).get("decision", "unknown")

                        with st.expander(f"{inv_num}  —  {ts}  —  {decision.upper()}"):
                            st.json(log_data)
                    except Exception as e:
                        st.markdown(f'<div style="color:#ef4444;font-size:0.75rem;">Error reading {log_file.name}: {e}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-family:IBM Plex Mono,monospace;font-size:0.8rem;color:#64748b;">Logs directory not found.</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()