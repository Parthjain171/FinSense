"""
Tests for financial document chunking logic.
"""

from app.rag.chunker import chunk_invoice


def test_chunker_preserves_table_headers():
    parsed_doc = {
        "metadata": {
            "client": "NovaByte",
            "invoice_number": "INV-101",
            "period": "March 2026",
            "total": "$15,000",
        },
        "source_file": "novabyte_march.pdf",
        "raw_text": "Invoice summary and details...",
        "tables": [
            [
                ["Description", "Rate", "Amount"],
                ["AWS Infrastructure", "$10,000", "$10,000"],
            ]
        ],

    }

    chunks = chunk_invoice(parsed_doc)

    # Find the line items chunk
    table_chunk = next(c for c in chunks if c["metadata"]["type"] == "invoice_line_items")
    assert "Description | Rate | Amount" in table_chunk["text"]
    assert "AWS Infrastructure | $10,000 | $10,000" in table_chunk["text"]


def test_chunk_size_stays_within_token_limit():
    parsed_doc = {
        "metadata": {"client": "NovaByte", "period": "March 2026"},
        "source_file": "novabyte_march.pdf",
        "raw_text": "Line of text. " * 500,
        "tables": [],
    }

    chunks = chunk_invoice(parsed_doc)

    for chunk in chunks:
        # Assuming ~4 chars per token, max ~500 tokens is roughly 2000 chars
        word_count = len(chunk["text"].split())
        assert word_count < 1000  # Stays comfortably within token limit


def test_metadata_includes_client_name_and_period():
    parsed_doc = {
        "metadata": {
            "client": "GreenThread",
            "period": "February 2026",
            "invoice_number": "INV-202",
        },
        "source_file": "greenthread_feb.pdf",
        "raw_text": "GreenThread invoice contents...",
        "tables": [],
    }

    chunks = chunk_invoice(parsed_doc)

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk["metadata"]["client"] == "GreenThread"
        assert chunk["metadata"]["period"] == "February 2026"
