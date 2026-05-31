from pathlib import Path
from typing import Literal

FormatType = Literal["pdf", "json", "xml", "tsv", "txt", "unknown"]


def detect_format(file_path: str) -> FormatType:
    """
    Detect invoice file format from extension and content.
    Returns format type string.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return "pdf"
    elif ext == ".json":
        return "json"
    elif ext == ".xml":
        return "xml"
    elif ext in [".csv", ".tsv"]:
        return "tsv"
    elif ext == ".txt":
        return "txt"
    else:
        # Try to detect from content
        try:
            content = path.read_text(encoding="utf-8", errors="ignore").strip()
            if content.startswith("{") or content.startswith("["):
                return "json"
            elif content.startswith("<?xml") or content.startswith("<invoice"):
                return "xml"
            elif "\t" in content[:200]:
                return "tsv"
            else:
                return "txt"
        except Exception:
            return "unknown"


def read_raw_text(file_path: str, format_type: FormatType) -> str:
    """
    Read raw content from file based on format.
    PDF uses pdfplumber, everything else reads as text.
    """
    if format_type == "pdf":
        return _read_pdf(file_path)
    else:
        return _read_text(file_path)


def _read_pdf(file_path: str) -> str:
    """Extract text from PDF using pdfplumber."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)
    except Exception as e:
        raise ValueError(f"Failed to read PDF {file_path}: {e}")


def _read_text(file_path: str) -> str:
    """Read any text-based file (TXT, JSON, XML, TSV)."""
    try:
        return Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise ValueError(f"Failed to read file {file_path}: {e}")