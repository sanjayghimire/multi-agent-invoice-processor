import os
from models.schemas import (
    ExtractedInvoice,
    ValidationResult,
    StockCheck,
    InvoiceState,
)
from database.queries import (
    get_inventory_item,
    get_all_inventory,
    is_duplicate_invoice,
)
from tools.normalizer import detect_fraud_signals


# ─── Math Verification ────────────────────────────────────────────────────────

def verify_math(invoice: ExtractedInvoice) -> tuple[bool, float, float]:
    """
    Independently recompute total from line items.
    Returns (is_correct, computed_total, discrepancy).
    """
    # Sum all line item totals
    computed = sum(item.total for item in invoice.items)

    # If stated total is higher, check if difference could be tax/shipping
    stated = invoice.stated_total
    discrepancy = round(abs(stated - computed), 2)

    # Allow tax and shipping on top of line items
    # Only flag if discrepancy is unexplained (not a round tax amount)
    # Phantom charge detection: flag if discrepancy > $10 AND
    # discrepancy doesn't match a reasonable tax rate (0-15%)
    if discrepancy <= 0.10:
        # Pure rounding
        return True, round(computed, 2), discrepancy

    # Check if discrepancy is explainable as tax
    if computed > 0:
        implied_rate = discrepancy / computed
        if 0 < implied_rate <= 0.15:
            # Looks like a legitimate tax rate
            return True, round(stated, 2), 0.0

    # Discrepancy is unexplained — flag it
    return False, round(computed, 2), discrepancy


# ─── Stock Checking ───────────────────────────────────────────────────────────

def check_stock(invoice: ExtractedInvoice) -> tuple[list[StockCheck], list[str]]:
    """
    Check each line item against inventory DB.
    Returns (stock_checks, unknown_items).
    """
    stock_checks = []
    unknown_items = []

    for item in invoice.items:
        db_item = get_inventory_item(item.item_name)

        if db_item is None:
            unknown_items.append(item.item_name)
            stock_checks.append(StockCheck(
                item_name=item.item_name,
                requested_qty=item.quantity,
                available_stock=0,
                is_sufficient=False,
                shortfall=item.quantity
            ))
        else:
            available = db_item["stock"]
            requested = item.quantity
            is_sufficient = available >= requested
            shortfall = max(0.0, requested - available)

            stock_checks.append(StockCheck(
                item_name=item.item_name,
                requested_qty=requested,
                available_stock=available,
                is_sufficient=is_sufficient,
                shortfall=shortfall
            ))

    return stock_checks, unknown_items


# ─── Fraud Scoring ────────────────────────────────────────────────────────────

def calculate_fraud_score(
    fraud_signals: list[str],
    unknown_items: list[str],
    stock_checks: list[StockCheck],
    math_verified: bool,
    invoice: ExtractedInvoice,
) -> float:
    """
    Calculate fraud risk score 0.0 to 1.0.
    Based on combination of signals.
    """
    score = 0.0

    # Fraud signals from text analysis
    score += min(len(fraud_signals) * 0.15, 0.45)

    # Unknown items (not in DB at all)
    score += min(len(unknown_items) * 0.20, 0.40)

    # Zero stock items
    zero_stock = [
        s for s in stock_checks
        if s.available_stock == 0 and s.requested_qty > 0
    ]
    score += min(len(zero_stock) * 0.20, 0.40)

    # Math discrepancy
    if not math_verified:
        score += 0.25

    # Missing vendor
    if not invoice.vendor or invoice.vendor == "Unknown":
        score += 0.20

    # Missing due date
    if not invoice.due_date:
        score += 0.05

    # Very high amount
    if invoice.stated_total > 50000:
        score += 0.10

    return min(round(score, 2), 1.0)


# ─── Main Validation Logic ────────────────────────────────────────────────────

def validate_invoice(invoice: ExtractedInvoice) -> ValidationResult:
    """
    Run all validation checks on extracted invoice.
    Returns ValidationResult with all findings.
    """
    flags = []

    # 1. Duplicate check
    is_duplicate = is_duplicate_invoice(invoice.invoice_number)
    if is_duplicate:
        flags.append(f"Duplicate invoice: {invoice.invoice_number} already processed")

    # 2. Stock checks
    stock_checks, unknown_items = check_stock(invoice)

    for check in stock_checks:
        if not check.is_sufficient:
            if check.available_stock == 0:
                flags.append(
                    f"{check.item_name}: zero stock (requested {check.requested_qty})"
                )
            else:
                flags.append(
                    f"{check.item_name}: need {check.requested_qty}, "
                    f"have {check.available_stock} "
                    f"(shortfall: {check.shortfall})"
                )

    for item in unknown_items:
        flags.append(f"Unknown item not in inventory: {item}")

    # 3. Math verification
    math_verified, computed_total, discrepancy = verify_math(invoice)
    if not math_verified:
        flags.append(
            f"Total mismatch: stated ${invoice.stated_total:.2f}, "
            f"computed ${computed_total:.2f}, "
            f"discrepancy ${discrepancy:.2f}"
        )

    # 4. Currency mismatch
    currency_mismatch = invoice.currency != "USD"
    if currency_mismatch:
        flags.append(f"Non-USD currency: {invoice.currency}")

    # 5. Negative quantities (already caught by Pydantic but double-check)
    for item in invoice.items:
        if item.quantity <= 0:
            flags.append(f"Invalid quantity for {item.item_name}: {item.quantity}")

    # 6. Missing critical fields
    if not invoice.vendor or invoice.vendor == "Unknown":
        flags.append("Missing vendor name")
    if not invoice.due_date:
        flags.append("Missing or unparseable due date")

    # 7. Fraud signals from extraction warnings
    fraud_signals = [
        w for w in invoice.extraction_warnings
        if any(word in w.lower() for word in
               ["urgent", "wire", "fraud", "suspicious", "caps", "exclamation"])
    ]

    # 8. Calculate overall fraud score
    fraud_score = calculate_fraud_score(
        fraud_signals=fraud_signals,
        unknown_items=unknown_items,
        stock_checks=stock_checks,
        math_verified=math_verified,
        invoice=invoice
    )

    # 9. Overall validity
    stock_failures = [s for s in stock_checks if not s.is_sufficient]
    is_valid = (
        len(stock_failures) == 0
        and len(unknown_items) == 0
        and math_verified
        and not currency_mismatch
        and not is_duplicate
        and fraud_score < 0.5
    )

    return ValidationResult(
        is_valid=is_valid,
        stock_checks=stock_checks,
        unknown_items=unknown_items,
        math_verified=math_verified,
        computed_total=computed_total,
        stated_total=invoice.stated_total,
        total_discrepancy=discrepancy,
        fraud_signals=fraud_signals,
        fraud_score=fraud_score,
        currency_mismatch=currency_mismatch,
        flags=flags,
        is_duplicate=is_duplicate
    )


# ─── LangGraph Node ───────────────────────────────────────────────────────────

def validation_node(state: dict) -> dict:
    """
    LangGraph node for invoice validation.
    Reads extracted invoice from state, runs all checks,
    returns updated state with validation result.
    """
    extracted = state.get("extracted_invoice")

    if not extracted:
        return {
            "validation_result": None,
            "error": "No extracted invoice to validate"
        }

    try:
        result = validate_invoice(extracted)
        return {"validation_result": result}
    except Exception as e:
        return {
            "validation_result": None,
            "error": f"Validation failed: {e}"
        }
