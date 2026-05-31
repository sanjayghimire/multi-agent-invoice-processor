# Token costs as of 2026 (per million tokens)
COSTS = {
    # Anthropic
    "claude-haiku-4-5":   {"input": 0.80,  "output": 4.00},
    "claude-sonnet-4-5":  {"input": 3.00,  "output": 15.00},
    # OpenAI
    "gpt-4o-mini":        {"input": 0.15,  "output": 0.60},
    "gpt-4o":             {"input": 2.50,  "output": 10.00},
    # Grok
    "grok-3-mini":        {"input": 0.30,  "output": 0.50},
    "grok-3":             {"input": 3.00,  "output": 15.00},
}


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int
) -> float:
    """Calculate USD cost for one LLM call."""
    if model not in COSTS:
        return 0.0
    rates = COSTS[model]
    cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
    return round(cost, 6)


def format_cost_report(
    total_invoices: int,
    total_cost: float
) -> str:
    """Generate a cost summary string."""
    per_invoice = total_cost / total_invoices if total_invoices > 0 else 0
    monthly_1k = per_invoice * 1000
    manual_monthly = 1000 * 4 * 25  # 1000 invoices × 4hrs × $25/hr

    return (
        f"LLM Cost Summary:\n"
        f"  Total invoices processed : {total_invoices}\n"
        f"  Total LLM cost           : ${total_cost:.4f}\n"
        f"  Cost per invoice         : ${per_invoice:.4f}\n"
        f"  Projected monthly (1K)   : ${monthly_1k:.2f}\n"
        f"  Manual cost monthly (1K) : ${manual_monthly:,.2f}\n"
        f"  ROI                      : {int(manual_monthly/monthly_1k):,}x"
        if monthly_1k > 0 else ""
    )