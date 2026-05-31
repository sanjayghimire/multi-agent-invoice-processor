import pdfplumber
from pathlib import Path


def extract_pdf_text(file_path: str) -> str:
    """
    Extract all text from a PDF file.
    Handles multi-page PDFs.
    Returns concatenated text from all pages.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    text_parts = []

    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            # Extract text
            text = page.extract_text()
            if text:
                text_parts.append(text)

            # Also try extracting tables
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if row:
                        clean_row = [
                            cell.strip() if cell else ""
                            for cell in row
                        ]
                        text_parts.append(" | ".join(clean_row))

    if not text_parts:
        raise ValueError(f"No text could be extracted from {file_path}")

    return "\n".join(text_parts)


def extract_pdf_tables(file_path: str) -> list[list]:
    """
    Extract tables from PDF as list of rows.
    Useful for structured invoice tables.
    """
    tables = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            tables.extend(page_tables)
    return tables