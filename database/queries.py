import sqlite3
from database.setup import get_connection


def get_inventory_item(item_name: str) -> dict | None:
    """Get a single inventory item by name."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT item, stock, unit_price, category FROM inventory WHERE item = ?",
        (item_name,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_inventory() -> list[dict]:
    """Get all inventory items."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT item, stock, unit_price, category FROM inventory")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def is_duplicate_invoice(invoice_number: str) -> bool:
    """Check if invoice was already processed."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM processed_invoices WHERE invoice_number = ?",
        (invoice_number,)
    )
    row = cursor.fetchone()
    conn.close()
    return row is not None


def save_processed_invoice(
    invoice_number: str,
    vendor: str,
    total_amount: float,
    currency: str,
    decision: str,
    risk_score: float,
    fraud_signals: str,
    processing_time_ms: int,
    llm_cost_usd: float
) -> None:
    """Save a processed invoice to audit trail."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO processed_invoices
        (invoice_number, vendor, total_amount, currency, decision,
         risk_score, fraud_signals, processing_time_ms, llm_cost_usd)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        invoice_number, vendor, total_amount, currency, decision,
        risk_score, fraud_signals, processing_time_ms, llm_cost_usd
    ))
    conn.commit()
    conn.close()


def save_rejected_invoice(
    invoice_number: str,
    reason: str,
    flags: str
) -> None:
    """Save rejection details."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO rejected_invoices (invoice_number, reason, flags)
        VALUES (?, ?, ?)
    """, (invoice_number, reason, flags))
    conn.commit()
    conn.close()