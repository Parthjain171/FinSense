"""
Financial-document-aware chunking.

Standard text splitters destroy financial documents because a line like
"$15,234" means nothing without its column header (AWS Infrastructure),
its row context (Operating Expenses), and its period (March 2026).

This chunker keeps that context intact by:
1. Prefixing every chunk with document metadata (client, period, type)
2. Keeping table headers attached to their data rows
3. Grouping related line items together
4. Never splitting mid-table
"""

from typing import List


def chunk_invoice(parsed_doc: dict) -> List[dict]:
    """
    Chunk a parsed invoice into retrieval-ready pieces.

    Each chunk gets a metadata prefix so the retriever always
    knows which client and which period a number belongs to.
    """
    chunks = []
    meta = parsed_doc.get("metadata", {})
    source = parsed_doc.get("source_file", "unknown")

    # Build a metadata prefix that goes on every chunk
    prefix_parts = []
    if meta.get("client"):
        prefix_parts.append(f"Client: {meta['client']}")
    if meta.get("invoice_number"):
        prefix_parts.append(f"Invoice: {meta['invoice_number']}")
    if meta.get("period"):
        prefix_parts.append(f"Period: {meta['period']}")
    if meta.get("total"):
        prefix_parts.append(f"Total: {meta['total']}")
    if meta.get("date"):
        prefix_parts.append(f"Date: {meta['date']}")

    prefix = " | ".join(prefix_parts)

    # Chunk 1: Full invoice summary (metadata + overview text)
    summary_text = f"{prefix}\n\n{parsed_doc['raw_text'][:1500]}"
    chunks.append({
        "text": summary_text,
        "metadata": {
            "source": source,
            "type": "invoice_summary",
            "client": meta.get("client", ""),
            "period": meta.get("period", ""),
            "invoice_number": meta.get("invoice_number", ""),
        }
    })

    # Chunk 2: Line items table (if tables were extracted)
    for table in parsed_doc.get("tables", []):
        if len(table) < 2:
            continue

        header = table[0]
        table_text = f"{prefix}\n\nLine Items:\n"
        table_text += " | ".join(header) + "\n"
        table_text += "-" * 50 + "\n"

        for row in table[1:]:
            table_text += " | ".join(row) + "\n"

        chunks.append({
            "text": table_text,
            "metadata": {
                "source": source,
                "type": "invoice_line_items",
                "client": meta.get("client", ""),
                "period": meta.get("period", ""),
                "invoice_number": meta.get("invoice_number", ""),
            }
        })

    # Chunk 3: Notes section (if present)
    raw = parsed_doc["raw_text"]
    if "Notes" in raw or "Add-on" in raw or "Scope" in raw:
        notes_start = raw.find("Notes")
        if notes_start == -1:
            notes_start = raw.find("Add-on")
        if notes_start == -1:
            notes_start = raw.find("Scope")
        if notes_start >= 0:
            notes_text = f"{prefix}\n\n{raw[notes_start:]}"
            chunks.append({
                "text": notes_text,
                "metadata": {
                    "source": source,
                    "type": "invoice_notes",
                    "client": meta.get("client", ""),
                    "period": meta.get("period", ""),
                    "invoice_number": meta.get("invoice_number", ""),
                }
            })

    return chunks


def chunk_financial_statement(parsed_doc: dict) -> List[dict]:
    """
    Chunk a financial statement (P&L, BS, CF) into retrieval-ready pieces.

    Keeps section headers with their data, never splits mid-section.
    """
    chunks = []
    source = parsed_doc.get("source_file", "unknown")
    doc_type = parsed_doc.get("type", "financial")
    client = parsed_doc.get("client", "")

    prefix = f"Client: {client} | Document: {doc_type} | File: {source}"

    raw = parsed_doc["raw_text"]
    lines = raw.strip().split("\n")

    # Group lines into sections based on ALL-CAPS headers
    current_section = []
    current_header = "Overview"
    sections = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect section headers (all uppercase, no numbers)
        is_header = (
            stripped.isupper()
            and not any(c.isdigit() for c in stripped)
            and len(stripped) > 3
        )

        if is_header and current_section:
            sections.append((current_header, current_section))
            current_section = []
            current_header = stripped
        else:
            current_section.append(stripped)

    if current_section:
        sections.append((current_header, current_section))

    # Each section becomes a chunk with the prefix and header
    for header, section_lines in sections:
        section_text = f"{prefix}\n\nSection: {header}\n"
        section_text += "\n".join(section_lines)

        chunks.append({
            "text": section_text,
            "metadata": {
                "source": source,
                "type": doc_type,
                "section": header,
                "client": client,
            }
        })

    # Also create one full-document chunk for broad queries
    full_text = f"{prefix}\n\n{raw}"
    if len(full_text) > 3000:
        full_text = full_text[:3000]

    chunks.append({
        "text": full_text,
        "metadata": {
            "source": source,
            "type": f"{doc_type}_full",
            "client": client,
        }
    })

    return chunks
