from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app import crud, schemas
from app.models import Loan, RepaymentPlan, PosSwipe, CreditCard, CardInstallment, Mortgage, Income, Expense
from app.finance.snapshot_service import compute_snapshot

router = APIRouter(prefix="/finance", tags=["finance-dashboard"])


@router.get("/dashboard", response_model=schemas.DashboardSummary)
def get_dashboard(db: Session = Depends(get_db)):
    today = date.today()
    snap = crud.get_today_snapshot(db, today)
    if not snap:
        data = compute_snapshot(db, today)
        snap = crud.create_snapshot(db, data)

    total_income = db.query(func.coalesce(func.sum(Income.amount), 0)).scalar() or 0

    month_start = today.replace(day=1)
    monthly_interest = db.query(func.coalesce(func.sum(RepaymentPlan.interest), 0)).filter(
        RepaymentPlan.status == "pending",
        RepaymentPlan.due_date >= month_start,
        RepaymentPlan.due_date <= today.replace(day=28) + timedelta(days=7),
    ).scalar() or 0

    month_pos_fee = db.query(func.coalesce(func.sum(PosSwipe.fee), 0)).filter(
        func.strftime("%Y-%m", PosSwipe.swipe_date) == today.strftime("%Y-%m")
    ).scalar() or 0

    return {
        "total_debt": snap.total_debt,
        "total_assets": round(total_income, 2),
        "monthly_interest": round(monthly_interest, 2),
        "monthly_pos_fee": round(month_pos_fee, 2),
        "total_loan_debt": snap.loan_debt,
        "total_card_debt": snap.card_debt,
        "total_installment_debt": snap.installment_debt,
        "total_mortgage_debt": snap.mortgage_debt,
    }


@router.get("/repay-reminders", response_model=list[schemas.RepayReminderItem])
def get_repay_reminders(db: Session = Depends(get_db)):
    today = date.today()
    cutoff = today + timedelta(days=7)
    reminders = []

    rps = db.query(RepaymentPlan).filter(
        RepaymentPlan.status == "pending",
        RepaymentPlan.due_date >= today,
        RepaymentPlan.due_date <= cutoff,
    ).all()
    for rp in rps:
        reminders.append(schemas.RepayReminderItem(
            type="loan",
            name=f"贷款 #{rp.loan_id}",
            person_name=rp.person.name if rp.person else "",
            card_last4="",
            due_date=rp.due_date,
            amount=rp.total_amount,
            days_left=(rp.due_date - today).days,
        ))

    cards = db.query(CreditCard).filter(CreditCard.status == "active").all()
    for card in cards:
        due_this_month = date(today.year, today.month, min(card.due_day, 28))
        if today <= due_this_month <= cutoff and card.current_balance > 0:
            reminders.append(schemas.RepayReminderItem(
                type="card",
                name=card.bank,
                person_name=card.person.name if card.person else "",
                card_last4=card.card_number_last4,
                due_date=due_this_month,
                amount=card.current_balance,
                days_left=(due_this_month - today).days,
            ))

    installments = db.query(CardInstallment).filter(
        CardInstallment.paid_periods < CardInstallment.periods,
    ).all()
    for inst in installments:
        due_day = inst.card.due_day if inst.card else 1
        due_date_inst = date(today.year, today.month, min(due_day, 28))
        if today <= due_date_inst <= cutoff:
            reminders.append(schemas.RepayReminderItem(
                type="installment",
                name=f"{inst.card.bank if inst.card else ''} 分期",
                person_name=inst.person.name if inst.person else "",
                card_last4=inst.card.card_number_last4 if inst.card else "",
                due_date=due_date_inst,
                amount=inst.period_total,
                days_left=(due_date_inst - today).days,
            ))

    reminders.sort(key=lambda r: r.days_left)
    return reminders
