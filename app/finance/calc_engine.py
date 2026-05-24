"""Interest calculation engine — pure functions, no database dependency."""
import math
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


def convert_to_monthly_rate(rate: float, rate_type: str, amount: float = 0, periods: int = 0, method: str = "") -> float:
    """Convert various rate types to monthly rate."""
    if rate_type == "monthly":
        return rate
    if rate_type == "annual":
        return rate / 12.0
    if rate_type == "total_interest":
        return _derive_monthly_rate_from_total(rate, amount, periods, method)
    raise ValueError(f"Unknown rate_type: {rate_type}")


def _derive_monthly_rate_from_total(total_interest: float, amount: float, periods: int, method: str) -> float:
    """Derive monthly rate from total interest using binary search."""
    lo, hi = 0.0, 0.5
    for _ in range(60):
        mid = (lo + hi) / 2
        if method == "equal_installment":
            plan = calc_equal_installment_plan(amount, mid, periods, "2000-01-01")
        elif method == "interest_first":
            plan = calc_interest_first_plan(amount, mid, periods, "2000-01-01")
        elif method == "bullet":
            plan = calc_bullet_plan(amount, mid, periods, "2000-01-01")
        else:
            raise ValueError(f"Unknown method: {method}")
        calc_total = sum(p["interest"] for p in plan)
        if calc_total > total_interest:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def calc_equal_installment_plan(amount: float, monthly_rate: float, periods: int, start_date: str) -> list[dict]:
    """Calculate equal installment repayment plan. Returns list of period dicts."""
    if monthly_rate == 0:
        period_amount = amount / periods
        plans = []
        d = date.fromisoformat(start_date)
        for i in range(periods):
            plans.append({
                "period_no": i + 1,
                "due_date": str(d + relativedelta(months=i)),
                "principal": round(period_amount, 2),
                "interest": 0.0,
                "total_amount": round(period_amount, 2),
            })
        return plans

    period_payment = amount * monthly_rate * (1 + monthly_rate) ** periods / ((1 + monthly_rate) ** periods - 1)
    remaining = amount
    plans = []
    d = date.fromisoformat(start_date)
    for i in range(periods):
        interest = round(remaining * monthly_rate, 2)
        principal = round(period_payment - interest, 2)
        remaining -= principal
        plans.append({
            "period_no": i + 1,
            "due_date": str(d + relativedelta(months=i)),
            "principal": principal,
            "interest": interest,
            "total_amount": round(principal + interest, 2),
        })
    return plans


def calc_interest_first_plan(amount: float, monthly_rate: float, periods: int, start_date: str) -> list[dict]:
    """Interest-first: pay interest each period, principal at the end."""
    period_interest = round(amount * monthly_rate, 2)
    plans = []
    d = date.fromisoformat(start_date)
    for i in range(periods - 1):
        plans.append({
            "period_no": i + 1,
            "due_date": str(d + relativedelta(months=i)),
            "principal": 0,
            "interest": period_interest,
            "total_amount": period_interest,
        })
    plans.append({
        "period_no": periods,
        "due_date": str(d + relativedelta(months=periods - 1)),
        "principal": amount,
        "interest": period_interest,
        "total_amount": round(amount + period_interest, 2),
    })
    return plans


def calc_bullet_plan(amount: float, monthly_rate: float, periods: int, start_date: str) -> list[dict]:
    """Bullet repayment: single payment at the end with all principal + accumulated interest."""
    total_interest = round(amount * monthly_rate * periods, 2)
    d = date.fromisoformat(start_date)
    return [{
        "period_no": 1,
        "due_date": str(d + relativedelta(months=periods - 1)),
        "principal": amount,
        "interest": total_interest,
        "total_amount": round(amount + total_interest, 2),
    }]


def calc_installment_annual_rate(period_rate: float, periods: int) -> float:
    """Calculate actual annual rate for credit card installments.
    Formula: period_rate * periods * 24 / (periods + 1)"""
    return period_rate * periods * 24.0 / (periods + 1)


def calc_pos_fee(amount: float, fee_rate: float) -> float:
    """Calculate POS swipe fee."""
    return round(amount * fee_rate, 2)
