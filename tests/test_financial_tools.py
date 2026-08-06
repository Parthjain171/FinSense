"""
Tests for financial calculation tools.
"""

from app.tools.financial_tools import (
    calculate_burn_rate,
    calculate_runway,
    calculate_gross_margin,
    flag_anomalies,
)


def test_burn_rate_returns_correct_value():
    sample_pl_data = {
        "January": {"Revenue": 10000, "NET INCOME (LOSS)": -5000},
        "February": {"Revenue": 12000, "NET INCOME (LOSS)": -7000},
    }
    result = calculate_burn_rate(sample_pl_data, ["January", "February"])

    assert result["January"]["burn_rate"] == 5000
    assert result["February"]["burn_rate"] == 7000
    assert result["average_monthly_burn"] == 6000


def test_runway_returns_correct_value():
    cash_balance = 120000.0
    monthly_burn = 10000.0

    result = calculate_runway(cash_balance, monthly_burn)

    assert result["cash_balance"] == cash_balance
    assert result["monthly_burn"] == monthly_burn
    assert result["months"] == 12.0
    assert "12.0 months" in result["summary"]


def test_gross_margin_returns_correct_value():
    sample_pl_data = {
        "January": {
            "Revenue": 10000.0,
            "Cost of Goods Sold": 3000.0,
            "GROSS PROFIT": 7000.0,
        }
    }
    result = calculate_gross_margin(sample_pl_data)

    assert "January" in result
    assert result["January"]["revenue"] == 10000.0
    assert result["January"]["cogs"] == 3000.0
    assert result["January"]["gross_profit"] == 7000.0
    assert result["January"]["gross_margin_pct"] == 70.0


def test_anomaly_detector_flags_known_outlier():
    # Expense jumps by >30% and >$2000 change
    sample_pl_data = {
        "January": {"AWS Infrastructure": 10000.0},
        "February": {"AWS Infrastructure": 25000.0},
    }

    anomalies = flag_anomalies(sample_pl_data, threshold_pct=30.0)

    assert len(anomalies) == 1
    assert anomalies[0]["category"] == "AWS Infrastructure"
    assert anomalies[0]["month"] == "February"
    assert anomalies[0]["previous"] == 10000.0
    assert anomalies[0]["current"] == 25000.0
    assert anomalies[0]["severity"] == "high"


def test_anomaly_detector_does_not_flag_normal_expense():
    # Normal minor expense variation (<30% change)
    sample_pl_data = {
        "January": {"AWS Infrastructure": 10000.0},
        "February": {"AWS Infrastructure": 10500.0},
    }

    anomalies = flag_anomalies(sample_pl_data, threshold_pct=30.0)

    assert len(anomalies) == 0
