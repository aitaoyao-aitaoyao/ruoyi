"""Debt snapshot computation service."""
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Loan, RepaymentPlan, CreditCard, CardInstallment, Mortgage, PosSwipe, CreditCardBill


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
            loan_debt += loan.amount

    # 信用卡负债 = 从未还账单计算（不包含已还清的账单）
    card_debt = 0.0
    active_cards = db.query(CreditCard).filter(CreditCard.status == "active").all()
    for card in active_cards:
        latest_bill = db.query(CreditCardBill).filter(
            CreditCardBill.card_id == card.id
        ).order_by(CreditCardBill.bill_month.desc()).first()
        if latest_bill and latest_bill.status != "paid":
            card_debt += max(0, latest_bill.bill_amount - latest_bill.paid_amount)

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
