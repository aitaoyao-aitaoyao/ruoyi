"""Debt snapshot computation service."""
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Loan, RepaymentPlan, CreditCard, CardInstallment, Mortgage, PosSwipe


def compute_snapshot(db: Session, snapshot_date: date) -> dict:
    """Compute all debt metrics for a given date. Returns a dict ready for DebtSnapshot."""
    # 贷款负债 = 待还本金（从还款计划中汇总），没有还款计划的用全额
    loan_debt = 0.0
    active_loans = db.query(Loan).filter(Loan.status == "active").all()
    for loan in active_loans:
        pending_principal = db.query(func.coalesce(func.sum(RepaymentPlan.principal), 0)).filter(
            RepaymentPlan.loan_id == loan.id,
            RepaymentPlan.status == "pending"
        ).scalar() or 0.0
        if pending_principal > 0:
            loan_debt += pending_principal
        else:
            # 没有还款计划或没有待还的，使用贷款全额
            loan_debt += loan.amount

    card_debt = db.query(func.coalesce(func.sum(CreditCard.current_balance), 0)).filter(
        CreditCard.status == "active"
    ).scalar() or 0.0

    installment_debt = 0.0
    installments = db.query(CardInstallment).all()
    for inst in installments:
        remaining = inst.amount - inst.period_principal * min(inst.paid_periods, inst.periods)
        if remaining > 0:
            installment_debt += remaining

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
