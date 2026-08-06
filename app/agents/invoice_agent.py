"""
Invoice Question Agent.

This is the core of what airCFO's HN post described:
"An agent that reads an inbound invoice question, pulls
the correct invoice, and drafts a context-aware reply."

It does not just retrieve and summarize. It follows the
same reasoning steps an experienced accountant would:

1. Parse the question to understand what the client wants
2. Identify the client and time period
3. Retrieve the right invoice(s)
4. If the question involves a comparison, also pull prior invoices
5. Analyze the data and figure out the answer
6. Draft a professional reply ready for a human to review and send
"""

import re
import os
import glob
from typing import Optional

from app.rag.pipeline import FinSenseRAG
from app.tools.financial_tools import (
    load_pl_data, calculate_burn_rate, calculate_runway,
    calculate_gross_margin, compare_periods, flag_anomalies,
)
from app.utils.llm_provider import get_llm_provider
from app.agents.prompts import (
    SYSTEM_PROMPT, INVOICE_EXPLANATION_PROMPT, INVOICE_COMPARISON_PROMPT,
    MONTH_END_ANALYSIS_PROMPT, DRAFT_REPLY_PROMPT, ANOMALY_EXPLANATION_PROMPT,
)


# Client metadata for quick lookups
CLIENT_INFO = {
    "novabyte": {
        "full_name": "NovaByte Inc.",
        "contact": "Aarav Mehta",
        "stage": "Seed",
        "cash_balance": 1800000,
        "base_monthly_fee": 5000,
    },
    "greenthread": {
        "full_name": "GreenThread Commerce LLC",
        "contact": "Priya Sharma",
        "stage": "Series A",
        "cash_balance": 3200000,
        "base_monthly_fee": 12000,
    },
    "pulsemetrics": {
        "full_name": "PulseMetrics Health Inc.",
        "contact": "Jordan Lee",
        "stage": "Pre-seed",
        "cash_balance": 520000,
        "base_monthly_fee": 3000,
    },
}

Q1_MONTHS = ["January", "February", "March"]
Q2_MONTHS = ["April", "May", "June"]
ALL_MONTHS = Q1_MONTHS + Q2_MONTHS


class InvoiceAgent:
    """
    Answers invoice and financial questions using RAG retrieval
    and financial calculation tools.

    Does not require an LLM API call for most queries. The agent
    logic is deterministic where possible (math, lookups) and
    only falls back to templates for natural language formatting.
    This keeps latency low and costs zero.
    """

    def __init__(self, rag: FinSenseRAG, data_dir: str):
        self.rag = rag
        self.data_dir = data_dir
        self.llm = get_llm_provider()

        # Pre-load financial data for all clients
        self.pl_data = {}
        fin_dir = os.path.join(data_dir, "sample_financials")
        for csv_path in glob.glob(os.path.join(fin_dir, "*_PL_*.csv")):
            filename = os.path.basename(csv_path)
            client_key = filename.split("_")[0].lower()
            self.pl_data[client_key] = load_pl_data(csv_path)

    def answer(self, question: str) -> dict:
        """
        Process a question end-to-end and return a structured response.

        Returns:
            dict with keys:
                - answer: the main response text
                - sources: list of source documents used
                - draft_reply: a formatted client email (if applicable)
                - metrics: any calculated metrics
                - reasoning: step-by-step reasoning trace
        """

        reasoning = []
        result = {
            "answer": "",
            "sources": [],
            "draft_reply": None,
            "metrics": None,
            "reasoning": [],
        }

        # Step 1: Parse the question
        q_lower = question.lower()
        client_key = self._detect_client(q_lower)
        month = self._detect_month(q_lower)
        question_type = self._classify_question(q_lower)

        reasoning.append(f"Detected client: {client_key or 'not specified'}")
        reasoning.append(f"Detected month: {month or 'not specified'}")
        reasoning.append(f"Question type: {question_type}")

        # Step 2: Route to the right handler
        if question_type == "invoice_explanation":
            result = self._handle_invoice_explanation(question, client_key, month, reasoning)
        elif question_type == "invoice_comparison":
            result = self._handle_invoice_comparison(question, client_key, month, reasoning)
        elif question_type == "burn_rate":
            result = self._handle_burn_rate(question, client_key, reasoning)
        elif question_type == "runway":
            result = self._handle_runway(question, client_key, reasoning)
        elif question_type == "anomaly":
            result = self._handle_anomaly(question, client_key, month, reasoning)
        elif question_type == "gross_margin":
            result = self._handle_gross_margin(question, client_key, reasoning)
        elif question_type == "period_comparison":
            result = self._handle_period_comparison(question, client_key, reasoning)
        elif question_type == "month_end":
            result = self._handle_month_end(question, client_key, month, reasoning)
        elif question_type == "draft_reply":
            result = self._handle_draft_reply(question, client_key, month, reasoning)
        else:
            result = self._handle_general(question, client_key, month, reasoning)

        result["reasoning"] = reasoning
        return result

    def _detect_client(self, text: str) -> Optional[str]:
        """Figure out which client the question is about."""
        for key in CLIENT_INFO:
            if key in text:
                return key
            # Also check full names
            full = CLIENT_INFO[key]["full_name"].lower()
            if full in text or full.split()[0].lower() in text:
                return key
        return None

    def _detect_month(self, text: str) -> Optional[str]:
        """Figure out which month the question refers to."""
        months = ["january", "february", "march", "april", "may", "june",
                  "july", "august", "september", "october", "november", "december"]
        for m in months:
            if m in text:
                return m.capitalize()
        return None

    def _classify_question(self, text: str) -> str:
        """Classify the question type to route to the right handler."""
        if any(w in text for w in ["explain", "break down", "breakdown", "line items", "charge", "what is the", "find", "search", "invoice"]):
            if any(w in text for w in ["higher", "lower", "more than", "less than", "vs", "compared"]):
                return "invoice_comparison"
            return "invoice_explanation"
        if any(w in text for w in ["burn rate", "burn"]):
            return "burn_rate"
        if any(w in text for w in ["runway"]):
            return "runway"
        if any(w in text for w in ["anomal", "unusual", "flag", "spike", "unexpected"]):
            return "anomaly"
        if any(w in text for w in ["gross margin", "margin trend"]):
            return "gross_margin"
        if any(w in text for w in ["q1 vs q2", "q1 versus q2", "quarter", "compare"]):
            return "period_comparison"
        if any(w in text for w in ["month-end", "month end", "summary", "generate"]):
            return "month_end"
        if any(w in text for w in ["draft", "reply", "respond", "email"]):
            return "draft_reply"
        if any(w in text for w in ["higher", "lower", "more", "increase", "went up", "why is"]):
            return "invoice_comparison"
        return "general"

    def _handle_invoice_explanation(self, question, client_key, month, reasoning):
        """Handle: 'Explain the $X charge on Client's Month invoice'"""
        reasoning.append("Retrieving invoice from FAISS index...")

        context = self.rag.retrieve_text(question, top_k=3, client_filter=client_key)
        sources = [r.get("metadata", {}).get("source", "") for r in self.rag.retrieve(question, client_filter=client_key)]

        reasoning.append(f"Retrieved {len(sources)} relevant chunks")
        reasoning.append("Generating explanation with LLM...")

        prompt = INVOICE_EXPLANATION_PROMPT.format(question=question, context=context)
        answer = self.llm.generate(SYSTEM_PROMPT, prompt)

        # Build a draft reply using LLM
        client_info = CLIENT_INFO.get(client_key, {})
        contact = client_info.get("contact", "there")

        reply_prompt = DRAFT_REPLY_PROMPT.format(
            question=question,
            contact_name=contact,
            context=context,
            metrics="N/A"
        )
        draft = self.llm.generate(SYSTEM_PROMPT, reply_prompt)

        return {
            "answer": answer,
            "sources": sources,
            "draft_reply": draft,
            "metrics": None,
        }

    def _handle_invoice_comparison(self, question, client_key, month, reasoning):
        """Handle: 'Why is this month higher than last month?'"""
        reasoning.append("This is a comparison question. Retrieving current and prior invoices...")

        context = self.rag.retrieve_text(question, top_k=5, client_filter=client_key)
        sources = [r.get("metadata", {}).get("source", "") for r in self.rag.retrieve(question, top_k=5, client_filter=client_key)]

        reasoning.append(f"Retrieved {len(sources)} chunks for comparison")
        reasoning.append("Generating comparison analysis with LLM...")

        prompt = INVOICE_COMPARISON_PROMPT.format(question=question, context=context)
        answer = self.llm.generate(SYSTEM_PROMPT, prompt)

        client_info = CLIENT_INFO.get(client_key, {})
        contact = client_info.get("contact", "there")

        reply_prompt = DRAFT_REPLY_PROMPT.format(
            question=question,
            contact_name=contact,
            context=context,
            metrics="N/A"
        )
        draft = self.llm.generate(SYSTEM_PROMPT, reply_prompt)

        return {
            "answer": answer,
            "sources": sources,
            "draft_reply": draft,
            "metrics": None,
        }

    def _handle_burn_rate(self, question, client_key, reasoning):
        """Handle: 'What is Client's burn rate?'"""
        if not client_key or client_key not in self.pl_data:
            return {"answer": "Could not identify the client. Please specify which client.", "sources": [], "draft_reply": None, "metrics": None}

        reasoning.append(f"Calculating burn rate from P&L data for {client_key}...")

        pl = self.pl_data[client_key]
        q1_burn = calculate_burn_rate(pl, Q1_MONTHS)
        q2_burn = calculate_burn_rate(pl, Q2_MONTHS)

        q1_avg = q1_burn.get("average_monthly_burn", 0)
        q2_avg = q2_burn.get("average_monthly_burn", 0)

        answer = (
            f"Burn rate analysis for {CLIENT_INFO[client_key]['full_name']}:\n\n"
            f"Q1 2026 average monthly burn: ${q1_avg:,}\n"
            f"Q2 2026 average monthly burn: ${q2_avg:,}\n\n"
        )

        if q2_avg > q1_avg:
            change = ((q2_avg - q1_avg) / q1_avg) * 100 if q1_avg > 0 else 0
            answer += f"Burn increased {change:.0f}% from Q1 to Q2."
        elif q2_avg < q1_avg:
            change = ((q1_avg - q2_avg) / q1_avg) * 100 if q1_avg > 0 else 0
            answer += f"Burn decreased {change:.0f}% from Q1 to Q2."
        else:
            answer += "Burn rate was stable between Q1 and Q2."

        return {
            "answer": answer,
            "sources": [f"{client_key}_PL_2026.csv"],
            "draft_reply": None,
            "metrics": {"q1_burn": q1_burn, "q2_burn": q2_burn},
        }

    def _handle_runway(self, question, client_key, reasoning):
        """Handle: 'How much runway does Client have?'"""
        if not client_key or client_key not in self.pl_data:
            return {"answer": "Could not identify the client. Please specify which client.", "sources": [], "draft_reply": None, "metrics": None}

        reasoning.append(f"Calculating runway for {client_key}...")

        pl = self.pl_data[client_key]
        burn = calculate_burn_rate(pl, ALL_MONTHS)
        avg_burn = burn.get("average_monthly_burn", 0)
        cash = CLIENT_INFO[client_key]["cash_balance"]

        runway = calculate_runway(cash, avg_burn)

        return {
            "answer": runway["summary"],
            "sources": [f"{client_key}_PL_2026.csv"],
            "draft_reply": None,
            "metrics": runway,
        }

    def _handle_anomaly(self, question, client_key, month, reasoning):
        """Handle: 'Flag anything unusual in Client's expenses'"""
        if not client_key or client_key not in self.pl_data:
            return {"answer": "Could not identify the client.", "sources": [], "draft_reply": None, "metrics": None}

        reasoning.append(f"Scanning for anomalies in {client_key} financials...")

        pl = self.pl_data[client_key]
        anomalies = flag_anomalies(pl)

        if month:
            anomalies = [a for a in anomalies if a["month"] == month]

        if not anomalies:
            answer = f"No significant anomalies detected in {CLIENT_INFO[client_key]['full_name']}'s expenses"
            if month:
                answer += f" for {month}"
            answer += "."
        else:
            # Use LLM to explain anomalies in plain English
            anomaly_text = "\n".join([f"- {a['note']}" for a in anomalies])
            prompt = ANOMALY_EXPLANATION_PROMPT.format(
                client_name=CLIENT_INFO[client_key]["full_name"],
                anomalies=anomaly_text,
            )
            answer = self.llm.generate(SYSTEM_PROMPT, prompt)

        return {
            "answer": answer,
            "sources": [f"{client_key}_PL_2026.csv"],
            "draft_reply": None,
            "metrics": {"anomalies": anomalies},
        }

    def _handle_gross_margin(self, question, client_key, reasoning):
        """Handle: 'What is Client's gross margin trend?'"""
        if not client_key or client_key not in self.pl_data:
            return {"answer": "Could not identify the client.", "sources": [], "draft_reply": None, "metrics": None}

        reasoning.append(f"Calculating gross margin trend for {client_key}...")

        pl = self.pl_data[client_key]
        margins = calculate_gross_margin(pl)

        answer = f"Gross margin trend for {CLIENT_INFO[client_key]['full_name']}:\n\n"
        for month, m in margins.items():
            answer += f"  {month}: {m['gross_margin_pct']}% (Revenue: ${m['revenue']:,}, COGS: ${m['cogs']:,})\n"

        return {
            "answer": answer,
            "sources": [f"{client_key}_PL_2026.csv"],
            "draft_reply": None,
            "metrics": margins,
        }

    def _handle_period_comparison(self, question, client_key, reasoning):
        """Handle: 'Compare Q1 vs Q2 for Client'"""
        if not client_key or client_key not in self.pl_data:
            return {"answer": "Could not identify the client.", "sources": [], "draft_reply": None, "metrics": None}

        reasoning.append(f"Comparing Q1 vs Q2 for {client_key}...")

        pl = self.pl_data[client_key]
        comparison = compare_periods(pl, Q1_MONTHS, Q2_MONTHS, "Q1 2026", "Q2 2026")

        answer = f"Q1 vs Q2 comparison for {CLIENT_INFO[client_key]['full_name']}:\n\n"
        for cat, vals in comparison.items():
            if abs(vals["delta"]) > 1000:
                direction = "up" if vals["delta"] > 0 else "down"
                answer += (
                    f"  {cat}: Q1 ${vals['Q1 2026']:,} -> Q2 ${vals['Q2 2026']:,} "
                    f"({direction} {abs(vals['pct_change'])}%)\n"
                )

        return {
            "answer": answer,
            "sources": [f"{client_key}_PL_2026.csv"],
            "draft_reply": None,
            "metrics": comparison,
        }

    def _handle_month_end(self, question, client_key, month, reasoning):
        """Handle: 'Generate month-end summary for Client'"""
        if not client_key or client_key not in self.pl_data:
            return {"answer": "Could not identify the client.", "sources": [], "draft_reply": None, "metrics": None}

        month = month or "March"
        reasoning.append(f"Generating month-end analysis for {client_key}, {month}...")

        pl = self.pl_data[client_key]
        if month not in pl:
            return {"answer": f"No data found for {month}.", "sources": [], "draft_reply": None, "metrics": None}

        d = pl[month]
        revenue = d.get("Revenue", 0)
        net = d.get("NET INCOME (LOSS)", 0)
        burn = abs(net) if net < 0 else 0
        total_opex = d.get("TOTAL OPERATING EXPENSES", 0)
        gross_profit = d.get("GROSS PROFIT", 0)
        margin = (gross_profit / revenue * 100) if revenue > 0 else 0

        # Find the biggest expense categories
        expense_cats = {k: v for k, v in d.items()
                       if k.startswith("  ") and isinstance(v, (int, float)) and v > 0}
        top_expenses = sorted(expense_cats.items(), key=lambda x: x[1], reverse=True)[:3]

        # Check for anomalies in this month
        anomalies = flag_anomalies(pl)
        month_anomalies = [a for a in anomalies if a["month"] == month]

        cash = CLIENT_INFO[client_key]["cash_balance"]
        all_burn = calculate_burn_rate(pl, ALL_MONTHS)
        avg_burn = all_burn.get("average_monthly_burn", 0)
        runway = calculate_runway(cash, avg_burn)

        answer = f"Month-End Analysis: {CLIENT_INFO[client_key]['full_name']} - {month} 2026\n\n"

        # Build a structured summary for the LLM
        financial_summary = (
            f"Revenue: ${revenue:,.0f}\n"
            f"Gross Profit: ${gross_profit:,.0f}\n"
            f"Gross Margin: {margin:.0f}%\n"
            f"Total Operating Expenses: ${total_opex:,.0f}\n"
            f"Net Income (Loss): ${net:,.0f}\n"
            f"Monthly Burn: ${burn:,.0f}\n"
            f"Cash Balance: ${cash:,.0f}\n"
            f"Average Monthly Burn: ${avg_burn:,.0f}\n"
            f"Estimated Runway: {runway['months']} months\n\n"
            f"Top Expenses:\n"
        )
        for cat, val in top_expenses:
            financial_summary += f"  {cat.strip()}: ${val:,.0f}\n"

        anomaly_text = "None" if not month_anomalies else "\n".join([f"- {a['note']}" for a in month_anomalies])

        prompt = MONTH_END_ANALYSIS_PROMPT.format(
            client_name=CLIENT_INFO[client_key]["full_name"],
            month=month,
            financial_summary=financial_summary,
            anomalies=anomaly_text,
        )

        llm_analysis = self.llm.generate(SYSTEM_PROMPT, prompt)
        answer += llm_analysis

        return {
            "answer": answer,
            "sources": [f"{client_key}_PL_2026.csv"],
            "draft_reply": None,
            "metrics": {"revenue": revenue, "burn": burn, "margin": margin, "runway": runway},
        }

    def _handle_draft_reply(self, question, client_key, month, reasoning):
        """Handle: 'Draft a reply to Client about their invoice question'"""
        reasoning.append("Drafting a client-facing reply with LLM...")

        context = self.rag.retrieve_text(question, top_k=3, client_filter=client_key)
        sources = [r.get("metadata", {}).get("source", "") for r in self.rag.retrieve(question, client_filter=client_key)]

        client_info = CLIENT_INFO.get(client_key, {})
        contact = client_info.get("contact", "there")

        reply_prompt = DRAFT_REPLY_PROMPT.format(
            question=question,
            contact_name=contact,
            context=context,
            metrics="N/A",
        )
        draft = self.llm.generate(SYSTEM_PROMPT, reply_prompt)

        return {
            "answer": f"Draft reply generated for {contact}. See draft_reply field.",
            "sources": sources,
            "draft_reply": draft,
            "metrics": None,
        }

    def _handle_general(self, question, client_key, month, reasoning):
        """Fallback handler for questions that do not match a specific type."""
        reasoning.append("General question. Using RAG retrieval...")

        context = self.rag.retrieve_text(question, top_k=5, client_filter=client_key)
        sources = [r.get("metadata", {}).get("source", "") for r in self.rag.retrieve(question, client_filter=client_key)]

        return {
            "answer": f"Here is what I found:\n\n{context}",
            "sources": sources,
            "draft_reply": None,
            "metrics": None,
        }
