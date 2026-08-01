"""
Extracts text and tables from invoice PDFs.
Preserves table structure so that line items stay connected
to their headers and amounts. This is critical for financial
documents where a number without its label is meaningless.
"""

import os
import pdfplumber


def extract_invoice_text(pdf_path: str) -> dict:
    """
    Extract structured content from an invoice PDF.

    Returns a dict with:
        - raw_text: full page text
        - tables: list of extracted tables (as list of rows)
        - metadata: invoice number, client, date, total parsed from text
        - source_file: the filename for citation
    """

    result = {
        "raw_text": "",
        "tables": [],
        "metadata": {},
        "source_file": os.path.basename(pdf_path),
    }

    with pdfplumber.open(pdf_path) as pdf:
        all_text = []
        all_tables = []

        for page in pdf.pages:
            text = page.extract_text() or ""
            all_text.append(text)

            tables = page.extract_tables()
            for table in tables:
                cleaned = []
                for row in table:
                    cleaned_row = [cell.strip() if cell else "" for cell in row]
                    if any(cleaned_row):
                        cleaned.append(cleaned_row)
                if cleaned:
                    all_tables.append(cleaned)

        result["raw_text"] = "\n".join(all_text)
        result["tables"] = all_tables

    # Parse metadata from the text
    text = result["raw_text"]
    result["metadata"] = _parse_invoice_metadata(text)

    return result


def _parse_invoice_metadata(text: str) -> dict:
    """Pull out key fields from invoice text."""

    meta = {}
    lines = text.split("\n")

    for line in lines:
        lower = line.lower().strip()
        if "invoice #:" in lower or "invoice#:" in lower:
            meta["invoice_number"] = line.split(":")[-1].strip()
        elif "client:" in lower:
            meta["client"] = line.split(":")[-1].strip()
        elif "period:" in lower:
            meta["period"] = line.split(":")[-1].strip()
        elif "date:" in lower and "due" not in lower:
            meta["date"] = line.split(":")[-1].strip()
        elif "due date:" in lower:
            meta["due_date"] = line.split(":")[-1].strip()
        elif "total due" in lower:
            # Try to grab the dollar amount
            parts = line.split()
            for part in parts:
                if "$" in part:
                    meta["total"] = part.strip()
                    break
        elif "contact:" in lower:
            meta["contact"] = line.split(":")[-1].strip()
        elif "stage:" in lower:
            meta["stage"] = line.split(":")[-1].strip()

    return meta


def extract_csv_financials(csv_path: str) -> dict:
    """
    Read a financial CSV (P&L, Balance Sheet, or Cash Flow)
    and return it as structured text with metadata.
    """
    import csv

    result = {
        "raw_text": "",
        "type": "",
        "client": "",
        "source_file": os.path.basename(csv_path),
    }

    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return result

    # First row is the title (e.g., "NovaByte Inc. - Profit & Loss Statement - H1 2026")
    title = rows[0][0] if rows[0] else ""
    result["raw_text"] = title + "\n\n"

    if "Profit & Loss" in title or "PL" in title:
        result["type"] = "profit_and_loss"
    elif "Balance Sheet" in title or "BS" in title:
        result["type"] = "balance_sheet"
    elif "Cash Flow" in title or "CF" in title:
        result["type"] = "cash_flow"

    # Extract client name from title
    if " - " in title:
        result["client"] = title.split(" - ")[0].strip()

    # Convert rows to readable text, preserving column alignment
    for row in rows[1:]:
        if any(cell.strip() for cell in row):
            line = " | ".join(cell.strip() for cell in row if cell.strip())
            result["raw_text"] += line + "\n"

    return result
