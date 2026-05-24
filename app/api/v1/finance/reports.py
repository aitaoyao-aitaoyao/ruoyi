from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.models import Loan, LoanPlatform, PosSwipe, Income, Expense, RepaymentPlan

router = APIRouter(prefix="/finance/reports", tags=["finance-reports"])


@router.get("/summary")
def report_summary(db: Session = Depends(get_db)):
    total_loans = db.query(func.coalesce(func.sum(Loan.amount), 0)).filter(Loan.status == "active").scalar() or 0
    total_pos_fee = db.query(func.coalesce(func.sum(PosSwipe.fee), 0)).scalar() or 0
    return {"total_active_loans": total_loans, "total_pos_fees": total_pos_fee}


@router.get("/by-platform")
def report_by_platform(db: Session = Depends(get_db)):
    results = db.query(
        LoanPlatform.name, func.coalesce(func.sum(Loan.amount), 0)
    ).join(Loan).filter(Loan.status == "active").group_by(LoanPlatform.name).all()
    return [{"platform": r[0], "total_amount": r[1]} for r in results]


@router.get("/by-month")
def report_by_month(db: Session = Depends(get_db)):
    results = db.query(
        func.strftime("%Y-%m", PosSwipe.swipe_date), func.coalesce(func.sum(PosSwipe.fee), 0)
    ).group_by(func.strftime("%Y-%m", PosSwipe.swipe_date)).order_by(
        func.strftime("%Y-%m", PosSwipe.swipe_date)
    ).all()
    return [{"month": r[0], "pos_fee": r[1]} for r in results]


@router.get("/gap-analysis")
def gap_analysis(year: int = Query(None), month: int = Query(None), db: Session = Depends(get_db)):
    if not year:
        year = date.today().year
    period_prefix = f"{year}-{month:02d}" if month else f"{year}-"

    income_total = db.query(func.coalesce(func.sum(Income.amount), 0)).filter(
        Income.period_value.like(f"{period_prefix}%")
    ).scalar() or 0

    expense_total = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.period_value.like(f"{period_prefix}%")
    ).scalar() or 0

    debt_payment = db.query(func.coalesce(func.sum(RepaymentPlan.total_amount), 0)).filter(
        RepaymentPlan.status == "pending"
    ).scalar() or 0

    total_expense = expense_total + debt_payment
    gap = income_total - total_expense

    return {
        "period": period_prefix.strip("%"),
        "total_income": income_total,
        "daily_expense": expense_total,
        "debt_payment": debt_payment,
        "total_expense": total_expense,
        "gap": gap,
    }
