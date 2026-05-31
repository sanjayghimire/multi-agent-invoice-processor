import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from models.schemas import ExtractedInvoice, LineItem, InvoiceState
from tools.format_router import detect_format, read_raw_text
from tools.normalizer import (
    normalize_item_name,
    normalize_amount,
    normalize_date,
    detect_fraud_signals,
    normalize_ocr_text,
)
from utils.cost_tracker import calculate_cost

load_dotenv()

# ─── LLM Factory ──────────────────────────────────────────────────────────────

def get_extraction_llm():
    """Return the configured LLM for extraction tasks."""
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    model = os.getenv("EXTRACTION_MODEL", "claude-haiku-4-5")

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


# ─── Format-Specific Pre-Parsers ──────────────────────────────────────────────

def preparse_json(raw_text: str) -> dict:
    """
    Handle JSON invoices including:
    - Single object
    - Array of objects (take last = most recent revision)
    - Two concatenated objects (INV-1004 pattern)
    """
    text = raw_text.strip()

    # Try direct parse first
    try:
        data = json.loads(text)
        if isinstance(data, list):
            # Array — take the last entry (most recent revision)
            return data[-1]
        return data
    except json.JSONDecodeError:
        pass

    # Try extracting all JSON objects
    objects = []
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(text[start:i+1])
                    objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = None

    if objects:
        # Return highest revision or last object
        for obj in reversed(objects):
            if obj.get("revision"):
                return obj
        return objects[-1]

    raise ValueError("Could not parse JSON from file")


def preparse_tsv(raw_text: str) -> dict:
    """
    Handle TSV/CSV invoices.
    Supports both:
    - Proper CSV with headers (INV-1007, INV-1015 pattern)
    - Flat key-value TSV with repeated keys (INV-1006 pattern)
    """
    lines = [l for l in raw_text.strip().splitlines() if l.strip()]
    if not lines:
        return {}

    # Detect if it's proper CSV with headers
    first_line = lines[0]
    delimiter = "," if "," in first_line else "\t"
    headers = [h.strip().lower() for h in first_line.split(delimiter)]

    # Proper CSV: has invoice-level headers in first row
    invoice_headers = ["invoice number", "invoice_number", "vendor", "date"]
    if any(h in headers for h in invoice_headers):
        return _parse_proper_csv(lines, delimiter)
    else:
        return _parse_flat_tsv(lines)


def _parse_proper_csv(lines: list, delimiter: str) -> dict:
    """Parse proper CSV with headers row (INV-1007, INV-1015 style)."""
    headers = [h.strip().lower().replace(" ", "_")
               for h in lines[0].split(delimiter)]

    result = {
        "invoice_number": None,
        "vendor": None,
        "date": None,
        "due_date": None,
        "line_items": [],
        "subtotal": 0.0,
        "tax_amount": 0.0,
        "total": 0.0,
    }

    for line in lines[1:]:
        cols = [c.strip() for c in line.split(delimiter)]
        if len(cols) < len(headers):
            cols += [""] * (len(headers) - len(cols))
        row = dict(zip(headers, cols))

        # Extract invoice-level fields from first data rows
        if row.get("invoice_number") or row.get("invoice_number") == "":
            inv_num = row.get("invoice_number", "").strip()
            if inv_num and not result["invoice_number"]:
                result["invoice_number"] = inv_num
            if row.get("vendor") and not result["vendor"]:
                result["vendor"] = row["vendor"].strip()
            if row.get("date") and not result["date"]:
                result["date"] = row["date"].strip()
            if row.get("due_date") and not result["due_date"]:
                result["due_date"] = row["due_date"].strip()

        # Extract line items
        item_col = row.get("item", "").strip()
        qty_col = row.get("qty", "").strip()
        price_col = row.get("unit_price", "").strip()
        total_col = row.get("line_total", "").strip()

        if item_col and qty_col and price_col:
            try:
                result["line_items"].append({
                    "item": item_col,
                    "quantity": float(qty_col),
                    "unit_price": float(price_col),
                    "total": float(total_col) if total_col else 0.0
                })
            except ValueError:
                pass

        # Extract totals from summary rows
        subtotal_col = row.get("subtotal:", row.get("subtotal", "")).strip()
        if subtotal_col:
            val = normalize_amount(subtotal_col)
            if val:
                result["subtotal"] = val

        # Check last two columns for summary rows
        if len(cols) >= 2:
            label = cols[-2].strip().lower().rstrip(":")
            value = cols[-1].strip()
            if "total" in label and "sub" not in label and "tax" not in label:
                val = normalize_amount(value)
                if val:
                    result["total"] = val
            elif "subtotal" in label:
                val = normalize_amount(value)
                if val:
                    result["subtotal"] = val
            elif "tax" in label:
                val = normalize_amount(value)
                if val:
                    result["tax_amount"] = val

    return result


def _parse_flat_tsv(lines: list) -> dict:
    """Parse flat key-value TSV with repeated keys (INV-1006 style)."""
    result = {
        "invoice_number": None,
        "vendor": None,
        "date": None,
        "due_date": None,
        "line_items": [],
        "subtotal": 0.0,
        "tax_amount": 0.0,
        "total": 0.0,
    }

    current_item = {}
    for line in lines:
        if "\t" in line:
            parts = line.split("\t", 1)
        elif "," in line:
            parts = line.split(",", 1)
        else:
            continue

        if len(parts) != 2:
            continue

        key = parts[0].strip().lower()
        value = parts[1].strip()

        if key == "invoice_number":
            result["invoice_number"] = value
        elif key == "vendor":
            result["vendor"] = value
        elif key == "date":
            result["date"] = value
        elif key == "due_date":
            result["due_date"] = value
        elif key == "item":
            # Save previous item if exists
            if current_item.get("item"):
                result["line_items"].append(current_item)
            current_item = {"item": value, "quantity": 0,
                           "unit_price": 0.0, "total": 0.0}
        elif key == "quantity":
            current_item["quantity"] = float(value) if value else 0
        elif key == "unit_price":
            current_item["unit_price"] = float(value) if value else 0.0
            current_item["total"] = (current_item["quantity"] *
                                     current_item["unit_price"])
        elif key == "subtotal":
            result["subtotal"] = float(value) if value else 0.0
        elif key == "tax":
            result["tax_amount"] = float(value) if value else 0.0
        elif key == "total":
            result["total"] = float(value) if value else 0.0

    # Don't forget last item
    if current_item.get("item"):
        result["line_items"].append(current_item)

    return result


def preparse_xml(raw_text: str) -> dict:
    """Parse XML invoice (INV-1014 style)."""
    root = ET.fromstring(raw_text)

    def find_text(element, *tags) -> Optional[str]:
        for tag in tags:
            el = element.find(".//" + tag)
            if el is not None and el.text:
                return el.text.strip()
        return None

    result = {
        "invoice_number": find_text(root, "invoice_number"),
        "vendor": find_text(root, "vendor"),
        "date": find_text(root, "date"),
        "due_date": find_text(root, "due_date"),
        "currency": find_text(root, "currency") or "USD",
        "line_items": [],
        "subtotal": float(find_text(root, "subtotal") or 0),
        "tax_amount": float(find_text(root, "tax_amount") or 0),
        "total": float(find_text(root, "total") or 0),
        "payment_terms": find_text(root, "payment_terms"),
    }

    for item in root.findall(".//item"):
        name = find_text(item, "name")
        qty = find_text(item, "quantity")
        price = find_text(item, "unit_price")
        if name and qty and price:
            quantity = float(qty)
            unit_price = float(price)
            result["line_items"].append({
                "item": name,
                "quantity": quantity,
                "unit_price": unit_price,
                "total": quantity * unit_price
            })

    return result


# ─── LLM Extraction ───────────────────────────────────────────────────────────

def extract_with_llm(raw_text: str, file_path: str) -> dict:
    """
    Use LLM to extract structured invoice data from text.
    Used for TXT and PDF formats where structure is unpredictable.
    """
    llm = get_extraction_llm()

    system_prompt = """You are an invoice data extraction specialist.
Extract structured data from invoice text, even if it contains:
- Typos and abbreviations (Vndr: = Vendor, Itms: = Items, Amt: = Amount)
- OCR artifacts (already pre-cleaned but may have residual issues)
- Email formatting (ignore email headers like From:, To:, Subject:)
- Informal language

Return ONLY a valid JSON object with these exact fields:
{
  "invoice_number": "string or null",
  "vendor": "string or null",
  "date": "string or null",
  "due_date": "string or null",
  "line_items": [
    {
      "item": "string",
      "quantity": number,
      "unit_price": number,
      "total": number
    }
  ],
  "subtotal": number,
  "tax_amount": number,
  "total": number,
  "currency": "USD",
  "payment_terms": "string or null",
  "notes": "string or null"
}

Rules:
- Normalize item names: remove spaces (Widget A → WidgetA)
- All amounts as plain numbers, no currency symbols
- If due_date is "yesterday" or unparseable, return null
- If vendor is empty or missing, return null
- Extract ALL line items even if invoice number or vendor is abbreviated
- Return ONLY the JSON, no explanation"""

    # Pre-clean OCR artifacts
    cleaned_text = normalize_ocr_text(raw_text)

    user_prompt = f"Extract invoice data from this text:\n\n{cleaned_text}"

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])

    # Parse response
    content = response.content.strip()
    # Strip markdown code blocks if present
    content = re.sub(r'^```json\s*', '', content)
    content = re.sub(r'^```\s*', '', content)
    content = re.sub(r'\s*```$', '', content)

    return json.loads(content)


# ─── Main Extraction Logic ─────────────────────────────────────────────────────

def extract_invoice(file_path: str) -> tuple[ExtractedInvoice, float]:
    """
    Main extraction function.
    Routes to right parser based on format.
    Returns (ExtractedInvoice, llm_cost_usd).
    """
    fmt = detect_format(file_path)
    raw_text = read_raw_text(file_path, fmt)
    llm_cost = 0.0
    warnings = []

    try:
        # Route to appropriate parser
        if fmt in ["json"]:
            data = preparse_json(raw_text)
        elif fmt in ["tsv"]:
            data = preparse_tsv(raw_text)
        elif fmt == "xml":
            data = preparse_xml(raw_text)
        else:
            # TXT and PDF → use LLM
            data = extract_with_llm(raw_text, file_path)
            model = os.getenv("EXTRACTION_MODEL", "claude-haiku-4-5")
            # Estimate tokens
            input_tokens = len(raw_text.split()) * 2
            output_tokens = 300
            llm_cost = calculate_cost(model, input_tokens, output_tokens)

        # Normalize and build line items
        line_items = []
        raw_items = data.get("line_items", [])

        # Aggregate quantities for same item (INV-1010, INV-1013 pattern)
        item_aggregates = {}
        for item_data in raw_items:
            raw_name = (item_data.get("item") or
                       item_data.get("name") or "Unknown")
            normalized_name = normalize_item_name(str(raw_name))
            qty = float(item_data.get("quantity", 0))
            price = float(item_data.get("unit_price", 0))
            total = float(item_data.get("total",
                         item_data.get("amount", qty * price)))

            if normalized_name not in item_aggregates:
                item_aggregates[normalized_name] = {
                    "item_name": normalized_name,
                    "quantity": 0,
                    "unit_price": price,
                    "total": 0,
                    "notes": item_data.get("note",
                             item_data.get("notes", None))
                }
            item_aggregates[normalized_name]["quantity"] += qty
            item_aggregates[normalized_name]["total"] += total

        for agg in item_aggregates.values():
            try:
                line_items.append(LineItem(**agg))
            except Exception as e:
                warnings.append(f"Skipped item {agg['item_name']}: {e}")

        # Parse dates
        raw_date = data.get("date") or data.get("invoice_date")
        raw_due = data.get("due_date")
        parsed_date = normalize_date(str(raw_date)) if raw_date else None
        parsed_due = normalize_date(str(raw_due)) if raw_due else None

        if raw_due and not parsed_due:
            warnings.append(f"Unparseable due date: '{raw_due}'")

        # Parse totals
        stated_total = normalize_amount(str(data.get("total", 0))) or 0.0

        # Extract vendor name (handle nested vendor object)
        vendor = data.get("vendor")
        if isinstance(vendor, dict):
            vendor = vendor.get("name", "Unknown")
        vendor = str(vendor).strip() if vendor else None

        if not vendor:
            warnings.append("Missing or empty vendor name")

        # Detect fraud signals
        fraud_signals = detect_fraud_signals(
            raw_text,
            vendor=vendor or ""
        )
        if fraud_signals:
            warnings.extend(fraud_signals)

        # Currency
        currency = str(data.get("currency", "USD")).upper()
        if currency != "USD":
            warnings.append(
                f"Non-USD currency detected: {currency}"
            )

        # Confidence score
        confidence = 1.0
        if warnings:
            confidence -= min(0.1 * len(warnings), 0.5)
        if not line_items:
            confidence = 0.0

        invoice_number = str(
            data.get("invoice_number") or
            Path(file_path).stem.replace("invoice_", "INV-").upper()
        )

        extracted = ExtractedInvoice(
            invoice_number=invoice_number,
            vendor=vendor or "Unknown",
            invoice_date=parsed_date,
            due_date=parsed_due,
            items=line_items,
            stated_total=stated_total,
            currency=currency,
            payment_terms=data.get("payment_terms"),
            notes=data.get("notes"),
            confidence_score=max(0.0, confidence),
            extraction_warnings=warnings,
            raw_text=raw_text[:500]  # Store first 500 chars for audit
        )

        return extracted, llm_cost

    except Exception as e:
        raise ValueError(
            f"Extraction failed for {file_path}: {e}"
        )


# ─── LangGraph Node ───────────────────────────────────────────────────────────

def ingestion_node(state: dict) -> dict:
    """
    LangGraph node for invoice ingestion.
    Reads state, extracts invoice, returns updated state.
    """
    invoice_path = state.get("invoice_path", "")

    try:
        extracted, llm_cost = extract_invoice(invoice_path)
        return {
            "extracted_invoice": extracted,
            "invoice_number": extracted.invoice_number,
            "llm_cost_usd": state.get("llm_cost_usd", 0.0) + llm_cost,
            "error": None
        }
    except Exception as e:
        return {
            "error": f"Ingestion failed: {e}",
            "extracted_invoice": None
        }