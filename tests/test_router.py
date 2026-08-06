"""
Tests for question router classification.
"""

from app.agents.invoice_agent import InvoiceAgent


def test_burn_rate_routes_to_financial_tools():
    question = "what's our burn rate"
    q_type = InvoiceAgent._classify_question(None, question.lower())
    assert q_type == "burn_rate"
    # Verify it routes to financial tools calculator rather than RAG retrieval
    assert q_type in ["burn_rate", "runway", "anomaly", "gross_margin", "period_comparison"]
    assert q_type != "general"


def test_find_invoice_routes_to_retrieval():
    question = "find NovaByte March invoice"
    q_type = InvoiceAgent._classify_question(None, question.lower())
    assert q_type == "invoice_explanation"
    # Verify it routes to document retrieval
    assert q_type in ["invoice_explanation", "general"]


def test_compare_expenses_routes_to_comparison():
    question = "compare Q1 vs Q2 expenses"
    q_type = InvoiceAgent._classify_question(None, question.lower())
    assert q_type in ["period_comparison", "invoice_comparison"]
