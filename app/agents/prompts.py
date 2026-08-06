"""
Prompt templates for the invoice agent.

Each template takes retrieved context and structured data,
then asks the LLM to synthesize a professional response.
Written the way an experienced accountant would talk
to a startup founder: direct, clear, no jargon overload.
"""

SYSTEM_PROMPT = """You are an AI financial document assistant for startup finance teams. You help accountants draft responses to client questions about invoices and financials.

Rules:
- Be direct and professional. No filler phrases.
- Always cite specific numbers from the provided context.
- When explaining charges, list each line item with its amount.
- When comparing periods, show the exact delta and percentage change.
- Never make up numbers. Only use what is in the provided context.
- Write like an accountant, not a chatbot. Warm but precise.
- Do not use em dashes. Use commas or periods instead."""


INVOICE_EXPLANATION_PROMPT = """A client is asking about their invoice. Using the context below, write a clear explanation of the charges.

Client Question: {question}

Retrieved Invoice Data:
{context}

Write a response that:
1. Acknowledges the question
2. Lists each line item with its amount
3. Explains any add-on charges and why they were incurred
4. States the total
5. Offers to discuss further if needed"""


INVOICE_COMPARISON_PROMPT = """A client wants to know why their invoice changed between periods. Using the context below, explain the difference.

Client Question: {question}

Retrieved Invoice Data (multiple periods):
{context}

Write a response that:
1. States what each invoice totaled
2. Identifies the exact line items that changed
3. Explains why the change happened (add-on services, scope changes, etc.)
4. Reassures the client that base services stayed the same if they did"""


MONTH_END_ANALYSIS_PROMPT = """Generate a CFO-level month-end financial analysis paragraph. This will be delivered to a startup founder, so it should be insightful but accessible.

Client: {client_name}
Period: {month} 2026

Financial Data:
{financial_summary}

Anomalies Detected:
{anomalies}

Write a 150-200 word analysis that covers:
1. Net burn and how it changed from the previous month
2. Revenue performance vs expectations
3. Gross margin
4. Top 3 expense categories
5. Any flagged anomalies with recommended action items
6. Current runway estimate
7. One forward-looking recommendation"""


DRAFT_REPLY_PROMPT = """Draft a professional email reply from a finance team member to a client. This reply will be reviewed by a human before sending.

Client Question: {question}
Client Name: {contact_name}

Retrieved Context:
{context}

Calculated Data:
{metrics}

Write the email reply. Include:
- A greeting using the client's first name
- A direct answer to their question with specific numbers
- Any relevant context (add-on services, scope changes, etc.)
- A closing that offers further help
- Sign off as "[Finance Team Member]" (the human reviewer adds their name)"""


ANOMALY_EXPLANATION_PROMPT = """Explain the following financial anomalies to a startup founder. Be specific about what happened and suggest what to investigate.

Client: {client_name}
Anomalies:
{anomalies}

For each anomaly, explain:
1. What changed and by how much
2. Whether this is likely a one-time event or a trend
3. What the founder should check or discuss with their team"""
