from datetime import date as date_type, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from dateutil.relativedelta import relativedelta
from app.db import get_db
from app.auth import get_current_user
from app.models import User, Loan, RepaymentPlan
from app import crud, schemas
from app.finance.calc_engine import convert_to_monthly_rate, calc_equal_installment_plan, calc_interest_first_plan, calc_bullet_plan

router = APIRouter(prefix="/finance/loans", tags=["finance-loans"])


def _fix_plan_dates(plan: list[dict]) -> list[dict]:
    """Convert string due_date to Python date objects."""
    for p in plan:
        p["due_date"] = date_type.fromisoformat(p["due_date"])
    return plan


@router.post("/", response_model=schemas.LoanRead, status_code=201)
def create_loan(data: schemas.LoanCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # 无固定期限的个人借贷：不生成还款计划
    if data.repay_method == "flexible" or data.periods <= 0:
        data.periods = 0
        data.rate = 0
        data.rate_type = "monthly"
        if not data.end_date:
            data.end_date = None
        return crud.create_loan(db, data, [])

    is_total_interest = data.rate_type == "total_interest"
    monthly_rate = convert_to_monthly_rate(
        rate=data.rate, rate_type=data.rate_type,
        amount=data.amount, periods=data.periods, method=data.repay_method,
    )
    if data.repay_method == "equal_installment":
        plan = calc_equal_installment_plan(data.amount, monthly_rate, data.periods, str(data.start_date))
    elif data.repay_method == "interest_first":
        plan = calc_interest_first_plan(data.amount, monthly_rate, data.periods, str(data.start_date))
    else:
        plan = calc_bullet_plan(data.amount, monthly_rate, data.periods, str(data.start_date))

    plan = _fix_plan_dates(plan)
    if not data.end_date:
        data.end_date = data.start_date + relativedelta(months=data.periods)
    # 如果使用总利息反推，将 rate_type 改为 monthly，rate 改为推导出的月利率
    if is_total_interest:
        data.rate = round(monthly_rate, 6)
        data.rate_type = "monthly"
    return crud.create_loan(db, data, plan)


@router.get("/", response_model=list[schemas.LoanRead])
def list_loans(person_id: int = Query(None), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """获取借款列表，同时自动标记所有已还期数"""
    _auto_pay_periods(db)
    return crud.get_loans(db, person_id)


def _auto_pay_periods(db: Session):
    """遍历所有活跃借款，将 paid_periods 范围内的待还计划自动标记为已还"""
    active_loans = db.query(Loan).filter(Loan.status == "active", Loan._paid_periods > 0).all()
    updated = False
    for loan in active_loans:
        paid_limit = loan.paid_periods  # 使用 property 获取真实已还数
        if paid_limit <= 0:
            continue
        pending = db.query(RepaymentPlan).filter(
            RepaymentPlan.loan_id == loan.id,
            RepaymentPlan.status == "pending",
            RepaymentPlan.period_no <= paid_limit
        ).all()
        for rp in pending:
            rp.status = "paid"
            rp.paid_date = rp.due_date  # 录入时即已还，用到期日
            updated = True
    if updated:
        db.commit()
    # 检查并自动结清贷款
    for loan in active_loans:
        if loan.paid_periods <= 0: continue
        all_paid = db.query(RepaymentPlan).filter(
            RepaymentPlan.loan_id == loan.id, RepaymentPlan.status == "pending"
        ).count() == 0
        if all_paid and loan.status == "active":
            loan.status = "closed"
            db.commit()


@router.get("/{loan_id}", response_model=schemas.LoanRead)
def get_loan(loan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    loan = crud.get_loan(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan


@router.get("/{loan_id}/repayments", response_model=list[schemas.RepaymentPlanRead])
def get_loan_repayments(loan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """获取还款计划，并自动标记已还期数（仅标记状态，不生成还款记录）"""
    loan = crud.get_loan(db, loan_id)
    if loan and loan.paid_periods > 0:
        # 自动将 paid_periods 范围内的 pending 计划标记为 paid，不创建任何还款交易记录
        pending_plans = db.query(RepaymentPlan).filter(
            RepaymentPlan.loan_id == loan_id,
            RepaymentPlan.status == "pending",
            RepaymentPlan.period_no <= loan.paid_periods
        ).all()
        for rp in pending_plans:
            rp.status = "paid"
            rp.paid_date = rp.due_date  # 使用到期日作为还款日，因为录入时就是已还的
        if pending_plans:
            db.commit()
    return crud.get_repayments(db, loan_id)


@router.post("/{loan_id}/regenerate-plan", response_model=list[schemas.RepaymentPlanRead])
def regenerate_plan(loan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """重新生成还款计划（基于当前贷款参数），已还期数自动标记"""
    loan = crud.get_loan(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    paid = loan.paid_periods or 0
    # Delete old plans
    crud.delete_repayments_for_loan(db, loan_id)
    # Calculate new plan
    monthly_rate = convert_to_monthly_rate(
        rate=loan.rate, rate_type=loan.rate_type,
        amount=loan.amount, periods=loan.periods, method=loan.repay_method,
    )
    if loan.repay_method == "equal_installment":
        plan = calc_equal_installment_plan(loan.amount, monthly_rate, loan.periods, str(loan.start_date))
    elif loan.repay_method == "interest_first":
        plan = calc_interest_first_plan(loan.amount, monthly_rate, loan.periods, str(loan.start_date))
    else:
        plan = calc_bullet_plan(loan.amount, monthly_rate, loan.periods, str(loan.start_date))
    plan = _fix_plan_dates(plan)
    # Create new repayment plans
    for i, p in enumerate(plan):
        status = "paid" if i < paid else "pending"
        paid_date = datetime.utcnow() if i < paid else None
        rp = RepaymentPlan(
            loan_id=loan.id, person_id=loan.person_id,
            period_no=p["period_no"], due_date=p["due_date"],
            principal=p["principal"], interest=p["interest"],
            total_amount=p["total_amount"], status=status,
            paid_date=paid_date,
        )
        db.add(rp)
    db.commit()
    return crud.get_repayments(db, loan_id)


@router.patch("/{loan_id}", response_model=schemas.LoanRead)
def update_loan(loan_id: int, data: schemas.LoanUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # 总利息反推：将总利息金额转换为月利率
    is_total_interest = data.rate_type == "total_interest"
    if is_total_interest and data.rate is not None:
        loan = crud.get_loan(db, loan_id)
        if not loan:
            raise HTTPException(status_code=404, detail="Loan not found")
        monthly_rate = convert_to_monthly_rate(
            rate=data.rate, rate_type="total_interest",
            amount=data.amount if data.amount is not None else loan.amount,
            periods=data.periods if data.periods is not None else loan.periods,
            method=data.repay_method if data.repay_method is not None else loan.repay_method,
        )
        data.rate = round(monthly_rate, 6)
        data.rate_type = "monthly"
    loan = crud.update_loan(db, loan_id, data)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan


@router.patch("/repayments/{repayment_id}/pay", response_model=schemas.RepaymentPlanRead)
def pay_repayment(repayment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rp = crud.pay_repayment(db, repayment_id)
    if not rp:
        raise HTTPException(status_code=404, detail="Repayment not found")
    return rp


@router.delete("/{loan_id}", status_code=204)
def delete_loan(loan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not crud.delete_loan(db, loan_id):
        raise HTTPException(status_code=404, detail="Loan not found")
