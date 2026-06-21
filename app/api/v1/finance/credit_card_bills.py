"""信用卡账单 API"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.auth import get_current_user
from app.models import User, CreditCard, CreditCardBill, PosSwipe, CreditCardTransaction
from app import crud, schemas

router = APIRouter(prefix="/finance/credit-card-bills", tags=["finance-credit-card-bills"])


def _auto_create_bill(db: Session, card: CreditCard, today: date = None):
    """如果当期账单不存在，自动创建"""
    if today is None:
        today = date.today()

    # 计算当期账单周期
    # 例如 bill_day=10, today=6月21日 → 当期: 5月11日~6月10日, 还款日: 7月
    # 例如 bill_day=10, today=6月5日 → 当期: 4月11日~5月10日, 还款日: 6月
    if today.day >= card.bill_day:
        # 本月账单日已过，当期=上月bill_day+1 ~ 本月bill_day
        bill_end = date(today.year, today.month, card.bill_day)
        bill_start = bill_end - relativedelta(months=1) + timedelta(days=1)
        bill_month = today.strftime("%Y-%m")
    else:
        # 本月账单日未到，当期=上上月bill_day+1 ~ 上月bill_day
        bill_end = date(today.year, today.month, card.bill_day) - relativedelta(months=1)
        bill_start = bill_end - relativedelta(months=1) + timedelta(days=1)
        bill_month = (today.replace(day=1) - relativedelta(months=1)).strftime("%Y-%m")

    # 检查是否已存在
    existing = db.query(CreditCardBill).filter(
        CreditCardBill.card_id == card.id,
        CreditCardBill.bill_month == bill_month,
    ).first()
    if existing:
        return existing

    # 自动汇总当期 POS刷卡 和 信用卡消费
    pos_total = db.query(func.coalesce(func.sum(PosSwipe.amount), 0)).filter(
        PosSwipe.card_id == card.id,
        PosSwipe.swipe_date >= bill_start,
        PosSwipe.swipe_date <= bill_end,
    ).scalar() or 0

    txn_total = db.query(func.coalesce(func.sum(CreditCardTransaction.amount), 0)).filter(
        CreditCardTransaction.card_id == card.id,
        CreditCardTransaction.trans_type == "消费",
        CreditCardTransaction.trans_date >= bill_start,
        CreditCardTransaction.trans_date <= bill_end,
    ).scalar() or 0

    bill_amount = round(pos_total + txn_total, 2)
    # 还款日：下个月的还
    due_year = bill_end.year
    due_month = bill_end.month + 1
    if due_month > 12:
        due_month = 1
        due_year += 1
    due_date_capped = min(card.due_day, 28)
    due_date = date(due_year, due_month, due_date_capped)

    bill = CreditCardBill(
        card_id=card.id,
        bill_month=bill_month,
        bill_start=bill_start,
        bill_end=bill_end,
        due_date=due_date,
        bill_amount=bill_amount,
        min_payment=round(bill_amount * 0.1, 2),
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


@router.get("/", response_model=list[schemas.CreditCardBillRead])
def list_bills(card_id: int = Query(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """获取某张信用卡的所有账单，自动创建当期账单"""
    card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="信用卡不存在")

    # 自动创建当期账单
    _auto_create_bill(db, card)

    return crud.get_credit_card_bills(db, card_id)


@router.get("/{bill_id}", response_model=schemas.CreditCardBillRead)
def get_bill(bill_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bill = crud.get_credit_card_bill(db, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")
    return bill


@router.patch("/{bill_id}", response_model=schemas.CreditCardBillRead)
def update_bill(bill_id: int, data: schemas.CreditCardBillUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """更新账单（录入金额、标记还款等）"""
    bill = crud.update_credit_card_bill(db, bill_id, data)
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")

    # 自动更新状态
    if bill.paid_amount >= bill.bill_amount and bill.bill_amount > 0:
        bill.status = "paid"
    elif bill.paid_amount > 0:
        bill.status = "partial"
    elif bill.due_date < date.today() and bill.bill_amount > 0:
        bill.status = "overdue"
    else:
        bill.status = "unpaid"
    db.commit()
    db.refresh(bill)
    return bill


@router.post("/{bill_id}/pay-full", response_model=schemas.CreditCardBillRead)
def pay_full(bill_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """一键全额还款"""
    bill = crud.get_credit_card_bill(db, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")
    bill.paid_amount = bill.bill_amount
    bill.status = "paid"
    db.commit()
    db.refresh(bill)
    return bill


@router.post("/{bill_id}/pay-minimum", response_model=schemas.CreditCardBillRead)
def pay_minimum(bill_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """一键最低还款"""
    bill = crud.get_credit_card_bill(db, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")
    bill.paid_amount = bill.min_payment
    bill.status = "partial"
    db.commit()
    db.refresh(bill)
    return bill


@router.post("/{bill_id}/undo-payment", response_model=schemas.CreditCardBillRead)
def undo_payment(bill_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """撤销还款"""
    bill = crud.get_credit_card_bill(db, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")
    bill.paid_amount = 0
    bill.status = "unpaid"
    db.commit()
    db.refresh(bill)
    return bill
