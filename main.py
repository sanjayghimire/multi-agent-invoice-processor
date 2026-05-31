import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description="Acme Corp Invoice Processing System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Single invoice:
    python main.py --invoice data/invoices/invoice_1001.txt

  Batch - all invoices:
    python main.py --batch

  Batch - specific folder:
    python main.py --batch --dir data/invoices

  Test single invoice (no LLM cost):
    python main.py --invoice data/invoices/invoice_1004.json
        """
    )

    parser.add_argument(
        "--invoice",
        type=str,
        help="Path to a single invoice file to process"
    )

    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process all invoices in the invoices directory"
    )

    parser.add_argument(
        "--dir",
        type=str,
        default="data/invoices",
        help="Directory containing invoices for batch mode (default: data/invoices)"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed output, show summary only"
    )

    args = parser.parse_args()

    # Validate API key
    provider = os.getenv("LLM_PROVIDER", "anthropic")
    key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "grok": "XAI_API_KEY"
    }
    required_key = key_map.get(provider)
    if required_key and not os.getenv(required_key):
        print(f"ERROR: Missing {required_key} in .env file")
        print(f"   Set LLM_PROVIDER={provider} and add your API key")
        sys.exit(1)

    from graph.pipeline import run_invoice, run_batch

    if args.invoice:
        # Single invoice mode
        path = Path(args.invoice)
        if not path.exists():
            print(f"ERROR: File not found: {args.invoice}")
            sys.exit(1)
        run_invoice(str(path), verbose=not args.quiet)

    elif args.batch:
        # Batch mode
        invoice_dir = Path(args.dir)
        if not invoice_dir.exists():
            print(f"ERROR: Directory not found: {args.dir}")
            sys.exit(1)

        # Get all invoice files
        extensions = [".txt", ".json", ".csv", ".xml", ".pdf"]
        invoice_files = []
        for ext in extensions:
            invoice_files.extend(sorted(invoice_dir.glob(f"*{ext}")))

        if not invoice_files:
            print(f"ERROR: No invoice files found in {args.dir}")
            sys.exit(1)

        # Filter out duplicates â€” prefer revised versions
        filtered = _filter_duplicates(invoice_files)
        print(f"Found {len(invoice_files)} files -> processing {len(filtered)} after dedup")

        run_batch([str(f) for f in filtered], verbose=not args.quiet)

    else:
        parser.print_help()


def _filter_duplicates(files: list) -> list:
    """
    Filter duplicate invoices â€” keep revised versions.
    invoice_1004_revised.json supersedes invoice_1004.json
    Also skip .txt versions when .pdf exists (same invoice).
    """
    file_map = {}

    for f in files:
        name = f.stem  # filename without extension

        # Check if this is a revised version
        if "_revised" in name:
            base = name.replace("_revised", "")
            file_map[base] = f  # revised supersedes original
        elif name not in file_map:
            file_map[name] = f
        else:
            # Keep revised, skip duplicate format
            existing = file_map[name]
            # Prefer PDF over TXT for same invoice
            if f.suffix == ".pdf" and existing.suffix == ".txt":
                file_map[name] = f
            # Keep existing if already revised
            elif "_revised" not in existing.stem:
                file_map[name] = f

    return sorted(file_map.values())


if __name__ == "__main__":
    main()
