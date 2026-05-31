import sqlite3
import os
from pathlib import Path

# Database will be created in the project root
DB_PATH = Path(__file__).parent.parent / "inventory.db"


def get_connection():
    """Get a database connection. Used by all agents."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn


def setup_database():
    """Create and seed the inventory database."""
    conn = get_connection()
    cursor = conn.cursor()

    # --- Inventory table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            item        TEXT PRIMARY KEY,
            stock       INTEGER NOT NULL,
            unit_price  REAL NOT NULL,
            category    TEXT DEFAULT 'general'
        )
    """)

    # --- Seed inventory (matches README exactly + unit prices) ---
    inventory_items = [
        ("WidgetA",  15, 250.00, "widget"),
        ("WidgetB",  10, 500.00, "widget"),
        ("GadgetX",   5, 750.00, "gadget"),
        ("FakeItem",  0,   0.00, "unknown"),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO inventory (item, stock, unit_price, category)
        VALUES (?, ?, ?, ?)
    """, inventory_items)

    # --- Processed invoices table (audit trail) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_invoices (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number      TEXT UNIQUE,
            vendor              TEXT,
            total_amount        REAL,
            currency            TEXT DEFAULT 'USD',
            decision            TEXT,
            risk_score          REAL,
            fraud_signals       TEXT,
            processing_time_ms  INTEGER,
            llm_cost_usd        REAL,
            processed_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- Rejected invoices table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rejected_invoices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number  TEXT,
            reason          TEXT,
            flags           TEXT,
            rejected_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print(f"✅ Database created at: {DB_PATH}")
    print("✅ Inventory seeded with: WidgetA(15), WidgetB(10), GadgetX(5), FakeItem(0)")
    print("✅ Tables created: inventory, processed_invoices, rejected_invoices")


def check_database():
    """Verify database contents — run after setup to confirm."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT item, stock, unit_price FROM inventory")
    rows = cursor.fetchall()

    print("\n📦 Current Inventory:")
    print(f"  {'Item':<12} {'Stock':>6} {'Unit Price':>12}")
    print(f"  {'-'*12} {'-'*6} {'-'*12}")
    for row in rows:
        print(f"  {row['item']:<12} {row['stock']:>6} ${row['unit_price']:>10.2f}")

    conn.close()


if __name__ == "__main__":
    setup_database()
    check_database()