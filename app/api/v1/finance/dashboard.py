from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.auth import get_current_user
from app.models import User
from app import crud, schemas
from app.models import Loan, RepaymentPlan, PosSwipe, CreditCard, CardInstallment, Mortgage, Income, Expense, CreditCardBill
from app.finance.snapshot_service import compute_snapshot

router = APIRouter(prefix="/finance", tags=["finance-dashboard"])


@router.get("/dashboard", response_model=schemas.DashboardSummary)
def get_dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    # 删除旧的今日快照，重新计算以反映最新数据
    snap = crud.get_today_snapshot(db, today)
    if snap:
        db.delete(snap)
        db.commit()
    data = compute_snapshot(db, today)
    snap = crud.create_snapshot(db, data)

    total_income = db.query(func.coalesce(func.sum(Income.amount), 0)).scalar() or 0

    month_start = today.replace(day=1)
    month_end = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    # 1. 贷款利息（当月待还还款计划，不跨月）
    loan_interest = db.query(func.coalesce(func.sum(RepaymentPlan.interest), 0)).filter(
        RepaymentPlan.status == "pending",
        RepaymentPlan.due_date >= month_start,
        RepaymentPlan.due_date <= month_end,
    ).scalar() or 0

    # 2. 分期手续费（当月到期的期数，检查全部分期）
    installments = db.query(CardInstallment).all()
    inst_fee = 0.0
    for inst in installments:
        if inst.total_fee <= 0:
            continue
        fee_per_period = inst.total_fee / inst.periods
        for n in range(1, inst.periods + 1):
            pd = inst.start_date + relativedelta(months=n - 1)
            if pd.year == today.year and pd.month == today.month:
                inst_fee += fee_per_period

    # 3. 房贷月利息
    mortgages = db.query(Mortgage).filter(Mortgage.status == "active").all()
    mtg_interest = sum(m.remaining_principal * m.rate / 12 for m in mortgages)

    monthly_interest = round(loan_interest + inst_fee + mtg_interest, 2)

    month_pos_fee = db.query(func.coalesce(func.sum(PosSwipe.fee), 0)).filter(
        func.strftime("%Y-%m", PosSwipe.swipe_date) == today.strftime("%Y-%m")
    ).scalar() or 0

    ex_mortgage = snap.total_debt - snap.mortgage_debt
    return {
        "total_debt": snap.total_debt,
        "total_debt_ex_mortgage": round(ex_mortgage, 2),
        "total_assets": round(total_income, 2),
        "monthly_interest": monthly_interest,
        "monthly_pos_fee": round(month_pos_fee, 2),
        "total_loan_debt": snap.loan_debt,
        "total_card_debt": snap.card_debt,
        "total_installment_debt": snap.installment_debt,
        "total_mortgage_debt": snap.mortgage_debt,
    }


@router.get("/repay-overdue")
def get_overdue_repayments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """获取逾期未还的还款计划"""
    today = date.today()
    items = db.query(RepaymentPlan).join(Loan).filter(
        RepaymentPlan.status == "pending",
        RepaymentPlan.due_date < today,
        RepaymentPlan.period_no > Loan._paid_periods,  # 只显示真正逾期的，已还期数范围内不显示
    ).order_by(RepaymentPlan.due_date).all()

    result = []
    for rp in items:
        loan = rp.loan
        platform_name = loan.platform.name if loan and loan.platform else ""
        days = (today - rp.due_date).days
        result.append({
            "id": rp.id, "loan_id": rp.loan_id, "period_no": rp.period_no,
            "amount": rp.total_amount or 0, "principal": rp.principal or 0, "interest": rp.interest or 0,
            "due_date": str(rp.due_date), "days_overdue": days,
            "name": f"{platform_name} 贷款" if platform_name else f"贷款 #{rp.loan_id}",
            "person_name": rp.person.name if rp.person else "",
        })
    return {"items": result, "total_overdue": len(result)}


@router.get("/repay-reminders", response_model=list[schemas.RepayReminderItem])
def get_repay_reminders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    cutoff = today + timedelta(days=7)
    reminders = []
    loan_map = {}

    # 每笔活跃贷款取最早待还，只收7天内的
    for loan in db.query(Loan).filter(Loan.status == "active").all():
        first_rp = db.query(RepaymentPlan).filter(
            RepaymentPlan.loan_id == loan.id,
            RepaymentPlan.status == "pending",
            RepaymentPlan.due_date >= today,
            RepaymentPlan.due_date <= cutoff
        ).order_by(RepaymentPlan.due_date).first()
        if not first_rp:
            continue
        platform_name = loan.platform.name if loan.platform else ""
        key = f"{platform_name}_{loan.person_id}"
        if key not in loan_map:
            loan_map[key] = {"name": f"{platform_name} 贷款" if platform_name else f"贷款 #{loan.id}",
                "person_name": loan.person.name if loan.person else "",
                "due_date": first_rp.due_date, "amount": 0, "days_left": 999}
        d = loan_map[key]
        d["amount"] += first_rp.total_amount
        d["due_date"] = min(d["due_date"], first_rp.due_date)
        d["days_left"] = min(d["days_left"], (first_rp.due_date - today).days)
    for d in loan_map.values():
            reminders.append(schemas.RepayReminderItem(
                type="loan", name=d["name"], person_name=d["person_name"],
                card_last4="", due_date=d["due_date"], amount=round(d["amount"], 2),
                days_left=max(0, d["days_left"]),
            ))

    # 信用卡 + 分期合并提醒（按卡汇总）
    cards = db.query(CreditCard).filter(CreditCard.status == "active").all()
    # 先按 card_id 收集基础信息
    card_map = {}  # card_id -> { bank, person_name, card_last4, due_date, amount, days_left }
    for card in cards:
        due_this_month = date(today.year, today.month, min(card.due_day, 28))
        if today <= due_this_month <= cutoff:
            # 用最新未还账单金额，不是卡余额
            bill_amount = card.current_balance
            latest_bill = db.query(CreditCardBill).filter(
                CreditCardBill.card_id == card.id,
                CreditCardBill.status != "paid"
            ).order_by(CreditCardBill.bill_month.desc()).first()
            if latest_bill:
                bill_amount = max(0, latest_bill.bill_amount - latest_bill.paid_amount)
            card_map[card.id] = {
                "bank": card.bank,
                "person_name": card.person.name if card.person else "",
                "card_last4": card.card_number_last4,
                "due_date": due_this_month,
                "amount": bill_amount,
                "days_left": (due_this_month - today).days,
            }

    # 把分期每期金额合并到对应卡上
    installments = db.query(CardInstallment).filter(
        CardInstallment.paid_periods < CardInstallment.periods,
    ).all()
    for inst in installments:
        due_day = inst.card.due_day if inst.card else 1
        due_date_inst = date(today.year, today.month, min(due_day, 28))
        if today <= due_date_inst <= cutoff:
            if inst.card_id in card_map:
                card_map[inst.card_id]["amount"] += inst.period_total
            else:
                # 该卡当前余额为 0 但有分期，也加入提醒
                bank_name = inst.card.bank if inst.card else ""
                card_tail = inst.card.card_number_last4 if inst.card else ""
                card_map[inst.card_id] = {
                    "bank": bank_name,
                    "person_name": inst.person.name if inst.person else "",
                    "card_last4": card_tail,
                    "due_date": due_date_inst,
                    "amount": inst.period_total,
                    "days_left": (due_date_inst - today).days,
                }

    for cid, cdata in card_map.items():
        if cdata["amount"] > 0:
            bank = cdata["bank"]
            tail = cdata["card_last4"]
            if bank and tail:
                display_name = f"{bank} 尾号{tail}"
            elif bank:
                display_name = bank
            elif tail:
                display_name = f"信用卡 尾号{tail}"
            else:
                display_name = f"信用卡 #{cid}"
            reminders.append(schemas.RepayReminderItem(
                type="card",
                name=display_name,
                person_name=cdata["person_name"],
                card_last4=cdata["card_last4"],
                due_date=cdata["due_date"],
                amount=round(cdata["amount"], 2),
                days_left=cdata["days_left"],
            ))

    reminders.sort(key=lambda r: r.days_left)
    return reminders


@router.get("/monthly-interest-detail")
def monthly_interest_detail(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """本月应付利息明细：贷款利息、分期手续费、房贷利息"""
    today = date.today()
    month_start = today.replace(day=1)
    month_end = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    items = []

    # 1. 贷款利息（当前窗口内待还的还款计划）
    loan_plans = db.query(RepaymentPlan).filter(
        RepaymentPlan.status == "pending",
        RepaymentPlan.due_date >= month_start,
        RepaymentPlan.due_date <= month_end,
    ).all()
    for rp in loan_plans:
        loan = rp.loan
        platform_name = loan.platform.name if loan and loan.platform else ""
        loan_label = f"{platform_name} 贷款" if platform_name else f"贷款 #{rp.loan_id}"
        items.append({
            "type": "贷款利息",
            "name": loan_label,
            "person_name": rp.person.name if rp.person else "",
            "due_date": str(rp.due_date),
            "amount": round(rp.interest, 2),
            "note": f"第{rp.period_no}/{loan.periods if loan else '?'}期",
        })

    # 2. 分期手续费（当月到期的期数对应的手续费，检查全部分期）
    installments = db.query(CardInstallment).all()
    for inst in installments:
        if inst.total_fee <= 0:
            continue
        fee_per_period = inst.total_fee / inst.periods
        count_this_month = 0
        for n in range(1, inst.periods + 1):
            pd = inst.start_date + relativedelta(months=n - 1)
            if pd.year == today.year and pd.month == today.month:
                count_this_month += 1
        if count_this_month > 0:
            card_info = f"{inst.card.bank} 尾号{inst.card.card_number_last4}" if inst.card else ""
            items.append({
                "type": "分期手续费",
                "name": card_info or f"分期 #{inst.id}",
                "person_name": inst.person.name if inst.person else "",
                "due_date": f"{today.year}-{today.month:02d}",
                "amount": round(fee_per_period * count_this_month, 2),
                "note": f"总额¥{int(inst.amount):,} {inst.periods}期 · 每期手续费¥{round(fee_per_period, 2)}",
            })

    # 3. 房贷月利息
    mortgages = db.query(Mortgage).filter(Mortgage.status == "active").all()
    for m in mortgages:
        monthly_int = m.remaining_principal * m.rate / 12
        items.append({
            "type": "房贷利息",
            "name": f"{m.bank} {m.house_name}",
            "person_name": m.person.name if m.person else "",
            "due_date": f"{today.year}-{today.month:02d}",
            "amount": round(monthly_int, 2),
            "note": f"剩余本金¥{int(m.remaining_principal):,}",
        })

    total = sum(it["amount"] for it in items)

    return {
        "period": f"{today.year}-{today.month:02d}",
        "total": round(total, 2),
        "items": items,
    }
