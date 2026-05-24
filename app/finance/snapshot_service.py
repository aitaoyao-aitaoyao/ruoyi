"""Debt snapshot computation service."""
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Loan, CreditCard, CardInstallment, Mortgage, PosSwipe


def compute_snapshot(db: Session, snapshot_date: date) -> dict:
    """Compute all debt metrics for a given date. Returns a dict ready for DebtSnapshot."""
    loan_debt = db.query(func.coalesce(func.sum(Loan.amount), 0)).filter(
        Loan.status == "active"
    ).scalar() or 0.0

    card_debt = db.query(func.coalesce(func.sum(CreditCard.current_balance), 0)).filter(
        CreditCard.status == "active"
    ).scalar() or 0.0

    installment_debt = db.query(
        func.coalesce(func.sum(CardInstallment.amount - CardInstallment.period_principal * CardInstallment.paid_periods), 0)
    ).scalar() or 0.0

    mortgage_debt = db.query(func.coalesce(func.sum(Mortgage.remaining_principal), 0)).filter(
        Mortgage.status == "active"
    ).scalar() or 0.0

    total_debt = loan_debt + card_debt + installment_debt + mortgage_debt

    pos_fee_total = db.query(func.coalesce(func.sum(PosSwipe.fee), 0)).scalar() or 0.0

    return {
        "snapshot_date": snapshot_date,
        "total_debt": round(total_debt, 2),
        "loan_debt": round(loan_debt, 2),
        "card_debt": round(card_debt, 2),
        "installment_debt": round(installment_debt, 2),
        "mortgage_debt": round(mortgage_debt, 2),
        "pos_fee_total": round(pos_fee_total, 2),
    }
