"""
Financial calculation tools.

These do the math that an accountant would do manually
when answering client questions. Burn rate, runway,
gross margin, period comparisons, anomaly flagging.

Each tool takes structured data and returns a plain-English
result that can go straight into a client reply.
"""

import csv
import os
from typing import Optional


def load_pl_data(csv_path: str) -> dict:
    """Load a P&L CSV into a structured dict keyed by month."""

    data = {}
    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 4:
        return data

    # Find the header row with month names
    header_row = None
    for i, row in enumerate(rows):
        if len(row) > 1 and any(m in str(row) for m in ["January", "February", "March", "April", "May", "June"]):
            header_row = i
            break

    if header_row is None:
        return data

    months = [col.strip() for col in rows[header_row][1:] if col.strip()]

    for month in months:
        data[month] = {}

    for row in rows[header_row + 1:]:
        if len(row) < 2:
            continue
        category = row[0].strip()
        if not category:
            continue

        for j, month in enumerate(months):
            if j + 1 < len(row) and row[j + 1].strip():
                try:
                    value = float(row[j + 1].strip().replace(",", ""))
                    data[month][category] = value
                except ValueError:
                    pass

    return data


def calculate_burn_rate(pl_data: dict, months: list) -> dict:
    """
    Calculate monthly burn rate for the given months.
    Burn rate = total expenses - revenue (net cash outflow).
    """

    results = {}
    for month in months:
        if month not in pl_data:
            continue
        d = pl_data[month]
        revenue = d.get("Revenue", 0)
        net = d.get("NET INCOME (LOSS)", 0)
        burn = abs(net) if net < 0 else 0
        results[month] = {
            "revenue": revenue,
            "net_income": net,
            "burn_rate": burn,
        }

    if results:
        avg_burn = sum(r["burn_rate"] for r in results.values()) / len(results)
        results["average_monthly_burn"] = round(avg_burn)

    return results


def calculate_runway(cash_balance: float, monthly_burn: float) -> dict:
    """
    Runway = cash balance / monthly burn rate.
    Returns months of runway and a plain English summary.
    """

    if monthly_burn <= 0:
        return {
            "months": float("inf"),
            "summary": f"The company is cash-flow positive with ${cash_balance:,.0f} in the bank. No burn to calculate runway against."
        }

    months = cash_balance / monthly_burn
    return {
        "cash_balance": cash_balance,
        "monthly_burn": monthly_burn,
        "months": round(months, 1),
        "summary": (
            f"With ${cash_balance:,.0f} in cash and a monthly burn of "
            f"${monthly_burn:,.0f}, the estimated runway is {months:.1f} months "
            f"(approximately {months / 12:.1f} years)."
        ),
    }


def calculate_gross_margin(pl_data: dict) -> dict:
    """Calculate gross margin for each month."""

    results = {}
    for month, d in pl_data.items():
        revenue = d.get("Revenue", 0)
        cogs = d.get("Cost of Goods Sold", 0)
        gross_profit = d.get("GROSS PROFIT", revenue - cogs)

        if revenue > 0:
            margin = (gross_profit / revenue) * 100
        else:
            margin = 0

        results[month] = {
            "revenue": revenue,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "gross_margin_pct": round(margin, 1),
        }

    return results


def compare_periods(pl_data: dict, period_1_months: list, period_2_months: list,
                    period_1_label: str = "Period 1", period_2_label: str = "Period 2") -> dict:
    """
    Compare two sets of months (e.g., Q1 vs Q2).
    Returns totals, deltas, and percentage changes for each category.
    """

    def sum_period(months):
        totals = {}
        for month in months:
            if month not in pl_data:
                continue
            for category, value in pl_data[month].items():
                totals[category] = totals.get(category, 0) + value
        return totals

    t1 = sum_period(period_1_months)
    t2 = sum_period(period_2_months)

    comparison = {}
    all_categories = set(list(t1.keys()) + list(t2.keys()))

    for cat in sorted(all_categories):
        v1 = t1.get(cat, 0)
        v2 = t2.get(cat, 0)
        delta = v2 - v1
        pct_change = ((delta / abs(v1)) * 100) if v1 != 0 else 0

        comparison[cat] = {
            period_1_label: round(v1),
            period_2_label: round(v2),
            "delta": round(delta),
            "pct_change": round(pct_change, 1),
        }

    return comparison


def flag_anomalies(pl_data: dict, threshold_pct: float = 30.0) -> list:
    """
    Detect unusual month-over-month changes in expense categories.
    Flags anything that jumps or drops more than threshold_pct
    compared to the previous month.
    """

    months = list(pl_data.keys())
    anomalies = []

    for i in range(1, len(months)):
        prev_month = months[i - 1]
        curr_month = months[i]
        prev_data = pl_data[prev_month]
        curr_data = pl_data[curr_month]

        for category in curr_data:
            if category in ["Revenue", "GROSS PROFIT", "NET INCOME (LOSS)",
                           "TOTAL OPERATING EXPENSES"]:
                continue  # Skip summary rows, only flag individual expenses

            prev_val = prev_data.get(category, 0)
            curr_val = curr_data.get(category, 0)

            if prev_val == 0:
                if curr_val > 5000:  # New expense > $5K
                    anomalies.append({
                        "month": curr_month,
                        "category": category.strip(),
                        "previous": prev_val,
                        "current": curr_val,
                        "change_pct": "New expense",
                        "severity": "medium",
                        "note": f"{category.strip()} appeared for the first time at ${curr_val:,.0f}",
                    })
                continue

            change_pct = ((curr_val - prev_val) / abs(prev_val)) * 100

            if abs(change_pct) >= threshold_pct and abs(curr_val - prev_val) > 2000:
                direction = "increase" if change_pct > 0 else "decrease"
                severity = "high" if abs(change_pct) >= 50 else "medium"

                anomalies.append({
                    "month": curr_month,
                    "category": category.strip(),
                    "previous": round(prev_val),
                    "current": round(curr_val),
                    "change_pct": round(change_pct, 1),
                    "severity": severity,
                    "note": (
                        f"{category.strip()} had a {abs(change_pct):.0f}% {direction} "
                        f"from ${prev_val:,.0f} to ${curr_val:,.0f} between "
                        f"{prev_month} and {curr_month}"
                    ),
                })

    anomalies.sort(key=lambda x: abs(x.get("change_pct", 0) if isinstance(x.get("change_pct"), (int, float)) else 100), reverse=True)
    return anomalies
