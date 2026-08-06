"""
Generates realistic sample invoices and financial statements
for three fictional airCFO startup clients.

Run this once to populate the data/ directory with PDFs and CSVs.
"""

import os
import csv
import json
import random
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---- Client Definitions ----

CLIENTS = {
    "NovaByte": {
        "full_name": "NovaByte Inc.",
        "stage": "Seed",
        "industry": "SaaS (Developer Tools)",
        "contact": "Aarav Mehta",
        "email": "aarav@novabyte.io",
        "base_monthly": 5000,
        "services": ["Monthly Accounting"],
        "monthly_revenue_range": (25000, 45000),
        "monthly_expense_range": (80000, 120000),
        "cash_balance": 1800000,
        "addons": {
            3: [("Tax Preparation (Q1 Filing)", 2500)],
            5: [("Series A Financial Model Buildout", 3000)],
        },
    },
    "GreenThread": {
        "full_name": "GreenThread Commerce LLC",
        "stage": "Series A",
        "industry": "E-commerce (Sustainable Fashion)",
        "contact": "Priya Sharma",
        "email": "priya@greenthread.com",
        "base_monthly": 8000,
        "services": ["Monthly Accounting", "Finance Advisory"],
        "monthly_revenue_range": (60000, 95000),
        "monthly_expense_range": (140000, 200000),
        "cash_balance": 3200000,
        "addons": {
            2: [("Audit Preparation (Annual)", 6000)],
            4: [("409A Valuation Support", 3500)],
        },
    },
    "PulseMetrics": {
        "full_name": "PulseMetrics Health Inc.",
        "stage": "Pre-seed",
        "industry": "HealthTech (Patient Analytics)",
        "contact": "Jordan Lee",
        "email": "jordan@pulsemetrics.health",
        "base_monthly": 3000,
        "services": ["Monthly Accounting"],
        "monthly_revenue_range": (5000, 15000),
        "monthly_expense_range": (40000, 65000),
        "cash_balance": 520000,
        "addons": {
            3: [("People Operations Setup", 2000)],
            6: [("Scope Reduction Adjustment", -500)],
        },
    },
}

MONTHS = [
    (2026, 1, "January"),
    (2026, 2, "February"),
    (2026, 3, "March"),
    (2026, 4, "April"),
    (2026, 5, "May"),
    (2026, 6, "June"),
]


def generate_invoice_pdf(client_key, client, year, month, month_name, invoice_num):
    """Generate a single invoice PDF for a client and month."""

    filename = f"INV-{year}-{invoice_num:04d}_{client_key}_{month_name}_{year}.pdf"
    filepath = os.path.join(SCRIPT_DIR, "sample_invoices", filename)

    doc = SimpleDocTemplate(filepath, pagesize=letter,
                            topMargin=50, bottomMargin=50,
                            leftMargin=50, rightMargin=50)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("InvTitle", parent=styles["Normal"],
                                 fontSize=22, fontName="Helvetica-Bold",
                                 spaceAfter=4)
    header_style = ParagraphStyle("InvHeader", parent=styles["Normal"],
                                  fontSize=9, textColor=colors.grey,
                                  leading=13)
    label_style = ParagraphStyle("Label", parent=styles["Normal"],
                                 fontSize=9, fontName="Helvetica-Bold")

    story = []

    # Header
    story.append(Paragraph("FinSense", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Cleveland, OH | hello@finsense.com | finsense.com", header_style))
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    story.append(Spacer(1, 15))

    # Invoice metadata
    invoice_date = datetime(year, month, 28)
    due_date = invoice_date + timedelta(days=15)

    meta_data = [
        ["INVOICE", "", "BILL TO", ""],
        [f"Invoice #: INV-{year}-{invoice_num:04d}", "",
         f"Client: {client['full_name']}", ""],
        [f"Date: {invoice_date.strftime('%B %d, %Y')}", "",
         f"Contact: {client['contact']}", ""],
        [f"Due Date: {due_date.strftime('%B %d, %Y')}", "",
         f"Email: {client['email']}", ""],
        [f"Period: {month_name} {year}", "",
         f"Stage: {client['stage']}", ""],
    ]

    meta_table = Table(meta_data, colWidths=[2.5 * inch, 0.5 * inch, 3 * inch, 0.5 * inch])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))

    # Line items
    line_items = []
    for svc in client["services"]:
        if svc == "Monthly Accounting":
            line_items.append((svc, f"{month_name} {year}", client["base_monthly"]))
        elif svc == "Finance Advisory":
            line_items.append((svc, f"{month_name} {year}", 4000))

    # Add-ons for this month
    addons = client.get("addons", {}).get(month, [])
    for addon_name, addon_amount in addons:
        line_items.append((addon_name, f"{month_name} {year}", addon_amount))

    total = sum(item[2] for item in line_items)

    table_data = [["Description", "Period", "Amount"]]
    for desc, period, amount in line_items:
        sign = "" if amount >= 0 else "-"
        table_data.append([desc, period, f"${abs(amount):,.2f}" if amount >= 0 else f"-${abs(amount):,.2f}"])

    table_data.append(["", "", ""])
    table_data.append(["", "TOTAL DUE", f"${total:,.2f}"])

    inv_table = Table(table_data, colWidths=[3.5 * inch, 1.5 * inch, 1.5 * inch])
    inv_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.lightgrey),
        ("FONTNAME", (1, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (-2, -1), (-1, -1), 11),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(inv_table)
    story.append(Spacer(1, 30))

    # Payment terms
    story.append(Paragraph("Payment Terms", label_style))
    story.append(Paragraph(
        "Net 15 from invoice date. Payment via ACH or wire transfer. "
        "Please reference the invoice number in your payment memo. "
        "Late payments are subject to a 1.5% monthly interest charge.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 15))

    # Notes
    if addons:
        story.append(Paragraph("Notes", label_style))
        for addon_name, addon_amount in addons:
            if addon_amount > 0:
                story.append(Paragraph(
                    f"Add-on service: {addon_name} was requested on "
                    f"{month_name} {random.randint(5, 20)}, {year} via email from {client['contact']}.",
                    styles["Normal"]
                ))
            else:
                story.append(Paragraph(
                    f"Scope adjustment: {addon_name} effective {month_name} 1, {year} "
                    f"as agreed in the service review call on {month_name} {random.randint(1,5)}, {year}.",
                    styles["Normal"]
                ))

    doc.build(story)
    return filename, total, line_items


def generate_financials_csv(client_key, client):
    """Generate P&L, Balance Sheet, and Cash Flow CSVs for a client."""

    random.seed(hash(client_key))
    financials_dir = os.path.join(SCRIPT_DIR, "sample_financials")

    # P&L Statement (monthly for 6 months)
    pl_rows = []
    pl_rows.append(["", "January", "February", "March", "April", "May", "June"])

    rev_base = client["monthly_revenue_range"][0]
    rev_growth = (client["monthly_revenue_range"][1] - rev_base) / 6

    exp_base = client["monthly_expense_range"][0]

    monthly_data = []
    for i, (yr, mo, mo_name) in enumerate(MONTHS):
        revenue = round(rev_base + rev_growth * i + random.uniform(-2000, 3000))
        cogs = round(revenue * random.uniform(0.22, 0.32))
        gross_profit = revenue - cogs

        payroll = round(exp_base * random.uniform(0.45, 0.55))
        rent = round(random.uniform(3000, 6000))
        aws = round(random.uniform(4000, 18000))
        marketing = round(random.uniform(2000, 8000))
        contractors = round(random.uniform(1000, 12000))
        software = round(random.uniform(1500, 4000))
        legal = round(random.uniform(500, 3000))
        other = round(random.uniform(500, 2500))

        # Add a spike in March for AWS (anomaly for detection)
        if mo == 3 and client_key == "NovaByte":
            aws = 15234

        total_opex = payroll + rent + aws + marketing + contractors + software + legal + other
        net_income = gross_profit - total_opex

        monthly_data.append({
            "month": mo_name,
            "revenue": revenue,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "payroll": payroll,
            "rent": rent,
            "aws": aws,
            "marketing": marketing,
            "contractors": contractors,
            "software": software,
            "legal": legal,
            "other": other,
            "total_opex": total_opex,
            "net_income": net_income,
        })

    # Write P&L CSV
    pl_path = os.path.join(financials_dir, f"{client_key}_PL_2026.csv")
    with open(pl_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([f"{client['full_name']} - Profit & Loss Statement - H1 2026"])
        writer.writerow([])
        header = ["Category"] + [d["month"] for d in monthly_data]
        writer.writerow(header)
        writer.writerow([])
        writer.writerow(["REVENUE"])
        writer.writerow(["  Revenue"] + [d["revenue"] for d in monthly_data])
        writer.writerow(["  Cost of Goods Sold"] + [d["cogs"] for d in monthly_data])
        writer.writerow(["GROSS PROFIT"] + [d["gross_profit"] for d in monthly_data])
        writer.writerow([])
        writer.writerow(["OPERATING EXPENSES"])
        writer.writerow(["  Payroll & Benefits"] + [d["payroll"] for d in monthly_data])
        writer.writerow(["  Rent & Facilities"] + [d["rent"] for d in monthly_data])
        writer.writerow(["  AWS Infrastructure"] + [d["aws"] for d in monthly_data])
        writer.writerow(["  Marketing & Ads"] + [d["marketing"] for d in monthly_data])
        writer.writerow(["  Contractors"] + [d["contractors"] for d in monthly_data])
        writer.writerow(["  Software & Tools"] + [d["software"] for d in monthly_data])
        writer.writerow(["  Legal & Professional"] + [d["legal"] for d in monthly_data])
        writer.writerow(["  Other Expenses"] + [d["other"] for d in monthly_data])
        writer.writerow(["TOTAL OPERATING EXPENSES"] + [d["total_opex"] for d in monthly_data])
        writer.writerow([])
        writer.writerow(["NET INCOME (LOSS)"] + [d["net_income"] for d in monthly_data])

    # Write Balance Sheet CSV (quarterly snapshots)
    bs_path = os.path.join(financials_dir, f"{client_key}_BS_2026.csv")
    cash = client["cash_balance"]
    with open(bs_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([f"{client['full_name']} - Balance Sheet - H1 2026"])
        writer.writerow([])
        writer.writerow(["Category", "Q1 2026 (Mar 31)", "Q2 2026 (Jun 30)"])
        writer.writerow([])
        writer.writerow(["ASSETS"])

        q1_burn = sum(d["net_income"] for d in monthly_data[:3])
        q2_burn = sum(d["net_income"] for d in monthly_data[3:])
        q1_cash = cash + q1_burn
        q2_cash = q1_cash + q2_burn

        writer.writerow(["  Cash & Equivalents", round(q1_cash), round(q2_cash)])
        writer.writerow(["  Accounts Receivable", round(q1_cash * 0.05), round(q2_cash * 0.06)])
        writer.writerow(["  Prepaid Expenses", round(random.uniform(5000, 15000)), round(random.uniform(5000, 15000))])
        q1_total_assets = round(q1_cash * 1.08)
        q2_total_assets = round(q2_cash * 1.09)
        writer.writerow(["TOTAL ASSETS", q1_total_assets, q2_total_assets])
        writer.writerow([])
        writer.writerow(["LIABILITIES"])
        writer.writerow(["  Accounts Payable", round(random.uniform(8000, 25000)), round(random.uniform(8000, 25000))])
        writer.writerow(["  Accrued Expenses", round(random.uniform(5000, 15000)), round(random.uniform(5000, 15000))])
        writer.writerow([])
        writer.writerow(["EQUITY"])
        writer.writerow(["  Paid-in Capital", cash, cash])
        writer.writerow(["  Retained Earnings", round(q1_burn), round(q1_burn + q2_burn)])

    # Write Cash Flow CSV
    cf_path = os.path.join(financials_dir, f"{client_key}_CF_2026.csv")
    with open(cf_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([f"{client['full_name']} - Cash Flow Statement - H1 2026"])
        writer.writerow([])
        writer.writerow(["Category", "Q1 2026", "Q2 2026"])
        writer.writerow([])
        writer.writerow(["OPERATING ACTIVITIES"])
        writer.writerow(["  Net Income (Loss)", round(q1_burn), round(q2_burn)])
        writer.writerow(["  Depreciation", round(random.uniform(500, 2000)), round(random.uniform(500, 2000))])
        writer.writerow(["  Changes in Working Capital", round(random.uniform(-5000, 5000)), round(random.uniform(-5000, 5000))])
        writer.writerow([])
        writer.writerow(["INVESTING ACTIVITIES"])
        writer.writerow(["  Equipment Purchases", round(random.uniform(-3000, 0)), round(random.uniform(-3000, 0))])
        writer.writerow([])
        writer.writerow(["FINANCING ACTIVITIES"])
        writer.writerow(["  Equity Raised", 0, 0])

    return monthly_data


def generate_sample_questions():
    """Generate sample questions with metadata for evaluation."""

    questions = [
        {
            "id": "q01",
            "question": "Can you explain the $12,500 charge on GreenThread's February invoice?",
            "expected_client": "GreenThread",
            "expected_month": "February",
            "expected_docs": ["INV-2026-0008_GreenThread_February_2026.pdf"],
            "type": "invoice_explanation"
        },
        {
            "id": "q02",
            "question": "Why is NovaByte's March invoice higher than February?",
            "expected_client": "NovaByte",
            "expected_month": "March",
            "expected_docs": ["INV-2026-0003_NovaByte_March_2026.pdf", "INV-2026-0002_NovaByte_February_2026.pdf"],
            "type": "invoice_comparison"
        },
        {
            "id": "q03",
            "question": "What services are included in PulseMetrics monthly retainer?",
            "expected_client": "PulseMetrics",
            "expected_docs": [],
            "type": "service_inquiry"
        },
        {
            "id": "q04",
            "question": "Break down the line items on GreenThread's April invoice",
            "expected_client": "GreenThread",
            "expected_month": "April",
            "type": "invoice_breakdown"
        },
        {
            "id": "q05",
            "question": "What was NovaByte's burn rate in Q1 vs Q2?",
            "expected_client": "NovaByte",
            "type": "metric_calculation"
        },
        {
            "id": "q06",
            "question": "How much runway does PulseMetrics have at current burn?",
            "expected_client": "PulseMetrics",
            "type": "metric_calculation"
        },
        {
            "id": "q07",
            "question": "Flag anything unusual in NovaByte's March expenses",
            "expected_client": "NovaByte",
            "expected_month": "March",
            "type": "anomaly_detection"
        },
        {
            "id": "q08",
            "question": "Generate a month-end summary for GreenThread for April 2026",
            "expected_client": "GreenThread",
            "expected_month": "April",
            "type": "month_end_analysis"
        },
        {
            "id": "q09",
            "question": "Compare GreenThread's Q1 vs Q2 revenue performance",
            "expected_client": "GreenThread",
            "type": "period_comparison"
        },
        {
            "id": "q10",
            "question": "How much did NovaByte spend on contractors in February?",
            "expected_client": "NovaByte",
            "expected_month": "February",
            "type": "specific_lookup"
        },
        {
            "id": "q11",
            "question": "What is GreenThread's gross margin trend over the last 6 months?",
            "expected_client": "GreenThread",
            "type": "trend_analysis"
        },
        {
            "id": "q12",
            "question": "Draft a reply to NovaByte asking why their May invoice includes a $3,000 charge they did not expect",
            "expected_client": "NovaByte",
            "expected_month": "May",
            "type": "draft_reply"
        },
        {
            "id": "q13",
            "question": "What was PulseMetrics total spend with FinSense in Q1 2026?",
            "expected_client": "PulseMetrics",
            "type": "total_spend"
        },
        {
            "id": "q14",
            "question": "PulseMetrics says they were charged for PeopleOps in March but did not sign up for it. Can you check?",
            "expected_client": "PulseMetrics",
            "expected_month": "March",
            "type": "dispute_check"
        },
        {
            "id": "q15",
            "question": "Pull up the latest invoice for each of our three clients",
            "expected_client": "all",
            "type": "multi_client_lookup"
        },
    ]

    questions_path = os.path.join(SCRIPT_DIR, "sample_questions", "questions.json")
    with open(questions_path, "w") as f:
        json.dump(questions, f, indent=2)

    return questions


def main():
    os.makedirs(os.path.join(SCRIPT_DIR, "sample_invoices"), exist_ok=True)
    os.makedirs(os.path.join(SCRIPT_DIR, "sample_financials"), exist_ok=True)
    os.makedirs(os.path.join(SCRIPT_DIR, "sample_questions"), exist_ok=True)

    invoice_num = 1
    all_invoices = []

    print("Generating sample invoices...")
    for client_key, client in CLIENTS.items():
        for year, month, month_name in MONTHS:
            filename, total, line_items = generate_invoice_pdf(
                client_key, client, year, month, month_name, invoice_num
            )
            all_invoices.append({
                "filename": filename,
                "client": client_key,
                "month": month_name,
                "year": year,
                "total": total,
                "line_items": [(d, p, a) for d, p, a in line_items],
            })
            print(f"  Created {filename} (${total:,.2f})")
            invoice_num += 1

    # Save invoice index
    index_path = os.path.join(SCRIPT_DIR, "sample_invoices", "invoice_index.json")
    with open(index_path, "w") as f:
        json.dump(all_invoices, f, indent=2, default=str)

    print("\nGenerating financial statements...")
    for client_key, client in CLIENTS.items():
        monthly_data = generate_financials_csv(client_key, client)
        print(f"  Created P&L, Balance Sheet, Cash Flow for {client_key}")

    print("\nGenerating sample questions...")
    questions = generate_sample_questions()
    print(f"  Created {len(questions)} evaluation questions")

    print(f"\nDone. Generated {len(all_invoices)} invoices, 9 financial statements, {len(questions)} questions.")


if __name__ == "__main__":
    main()
