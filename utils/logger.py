import json
import os
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def log_invoice_run(
    invoice_number: str,
    invoice_path: str,
    extracted: dict,
    validation: dict,
    approval: dict,
    payment: dict,
    processing_time_ms: int,
    llm_cost_usd: float
) -> str:
    """
    Write a complete audit log entry for one invoice run.
    Returns the log file path.
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "invoice_number": invoice_number,
        "invoice_path": invoice_path,
        "processing_time_ms": processing_time_ms,
        "llm_cost_usd": round(llm_cost_usd, 6),
        "pipeline": {
            "extraction": extracted,
            "validation": validation,
            "approval": approval,
            "payment": payment
        }
    }

    # One log file per invoice
    log_file = LOGS_DIR / f"{invoice_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, indent=2, default=str)

    return str(log_file)


def log_error(invoice_path: str, error: str) -> None:
    """Log a pipeline error."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "invoice_path": invoice_path,
        "error": error
    }
    log_file = LOGS_DIR / f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, indent=2)