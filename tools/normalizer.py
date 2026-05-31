import re
from typing import Optional


def normalize_ocr_text(text: str) -> str:
    """
    Fix common OCR corruption patterns before parsing.
    Example: '$3,500.O0' → '$3,500.00'
             '26-Jan-2O26' → '26-Jan-2026'
    """
    # Replace capital O with zero when surrounded by digits or decimals
    text = re.sub(r'(?<=[0-9])O(?=[0-9])', '0', text)
    text = re.sub(r'(?<=[0-9,\.])O(?=[0-9])', '0', text)
    text = re.sub(r'(?<=[0-9])O(?=[0-9,\.])', '0', text)

    # Fix common OCR letter/number swaps
    text = re.sub(r'\$([0-9,]+)\.([A-Z])([0-9])', lambda m:
        f"${m.group(1)}.0{m.group(3)}", text)

    return text


def normalize_item_name(name: str) -> str:
    """
    Normalize item names to match inventory DB keys.
    'Widget A' → 'WidgetA'
    'Gadget X' → 'GadgetX'
    'gadgetx'  → 'GadgetX' (fuzzy match)
    """
    # Remove legitimate parenthetical notes before matching inventory keys.
    normalized = re.sub(r'\s*\([^)]*\)', '', name).replace(" ", "").strip()

    # Known mappings for fuzzy matching
    known_items = {
        "widgeta": "WidgetA",
        "widgetb": "WidgetB",
        "gadgetx": "GadgetX",
        "fakeitem": "FakeItem",
    }

    return known_items.get(normalized.lower(), normalized)


def normalize_amount(amount_str: str) -> Optional[float]:
    """
    Parse amount strings safely.
    '$3,500.O0' → 3500.00
    '$9,975.00' → 9975.00
    '15000'     → 15000.00
    Returns None if unparseable.
    """
    if not amount_str:
        return None

    # Apply OCR fix first
    cleaned = normalize_ocr_text(str(amount_str))

    # Remove currency symbols, commas, spaces
    cleaned = re.sub(r'[,$€£\s]', '', cleaned)

    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_date(date_str: str) -> Optional[str]:
    """
    Parse various date formats → ISO format (YYYY-MM-DD).
    '26-Jan-2O26'  → '2026-01-26'
    'Jan 30 2026'  → '2026-01-30'
    '2026-01-15'   → '2026-01-15'
    'yesterday'    → None (unparseable, flagged)
    """
    if not date_str:
        return None

    # Apply OCR fix first
    cleaned = normalize_ocr_text(date_str.strip())

    # Try multiple formats
    from datetime import datetime

    formats = [
        "%Y-%m-%d",        # 2026-01-15
        "%d-%b-%Y",        # 26-Jan-2026
        "%b %d %Y",        # Jan 30 2026
        "%d/%m/%Y",        # 30/01/2026
        "%m/%d/%Y",        # 01/30/2026
        "%B %d, %Y",       # January 30, 2026
        "%d %B %Y",        # 30 January 2026
    ]

    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Could not parse
    return None


def detect_fraud_signals(text: str, vendor: str = "") -> list[str]:
    """
    Scan invoice text for fraud indicators.
    Returns list of signal descriptions found.
    """
    signals = []
    text_lower = text.lower()

    # Skip fraud detection for obviously legitimate notes
    legitimate_notes = [
        "rush order",
        "volume discount",
        "replacement",
        "expedited",
        "sample",
        "thank you",
    ]
    has_legitimate_note = any(note in text_lower for note in legitimate_notes)

    # Urgency language
    urgency_words = ["urgent", "immediately", "asap", "penalty", "penalties",
                     "overdue", "final notice", "last chance"]
    for word in urgency_words:
        if word in text_lower and not has_legitimate_note:
            signals.append(f"Urgency language detected: '{word}'")

    # Wire transfer preference
    if "wire transfer" in text_lower or "wire payment" in text_lower:
        signals.append("Wire transfer payment requested (fraud indicator)")

    # Suspicious payment terms
    if "immediate" in text_lower and "payment" in text_lower:
        signals.append("Immediate payment demanded")

    # Suspicious vendor names
    suspicious_vendor_words = ["fraudster", "scam", "fake", "test"]
    for word in suspicious_vendor_words:
        if word in vendor.lower():
            signals.append(f"Suspicious vendor name: '{vendor}'")

    # Excessive exclamation marks
    if text.count("!") >= 2:
        signals.append(f"Excessive exclamation marks ({text.count('!')} found)")

    # ALL CAPS sections (excluding normal headers)
    normal_headers = {
        "INVOICE",
        "TOTAL",
        "SUBTOTAL",
        "USD",
        "QTY",
        "RATE",
        "AMOUNT",
        "DESCRIPTION",
    }
    caps_pattern = re.findall(r'[A-Z]{5,}', text)
    caps_pattern = [word for word in caps_pattern if word not in normal_headers]
    if caps_pattern:
        signals.append(f"ALL CAPS text detected: {caps_pattern[:3]}")

    return signals
