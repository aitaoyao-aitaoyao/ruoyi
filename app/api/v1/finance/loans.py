from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas
from app.finance.calc_engine import convert_to_monthly_rate, calc_equal_installment_plan, calc_interest_first_plan, calc_bullet_plan

router = APIRouter(prefix="/finance/loans", tags=["finance-loans"])


@router.post("/", response_model=schemas.LoanRead, status_code=201)
def create_loan(data: schemas.LoanCreate, db: Session = Depends(get_db)):
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

    return crud.create_loan(db, data, plan)


@router.get("/", response_model=list[schemas.LoanRead])
def list_loans(person_id: int = Query(None), db: Session = Depends(get_db)):
    return crud.get_loans(db, person_id)


@router.get("/{loan_id}", response_model=schemas.LoanRead)
def get_loan(loan_id: int, db: Session = Depends(get_db)):
    loan = crud.get_loan(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan


@router.get("/{loan_id}/repayments", response_model=list[schemas.RepaymentPlanRead])
def get_loan_repayments(loan_id: int, db: Session = Depends(get_db)):
    return crud.get_repayments(db, loan_id)


@router.patch("/repayments/{repayment_id}/pay", response_model=schemas.RepaymentPlanRead)
def pay_repayment(repayment_id: int, db: Session = Depends(get_db)):
    rp = crud.pay_repayment(db, repayment_id)
    if not rp:
        raise HTTPException(status_code=404, detail="Repayment not found")
    return rp


@router.delete("/{loan_id}", status_code=204)
def delete_loan(loan_id: int, db: Session = Depends(get_db)):
    if not crud.delete_loan(db, loan_id):
        raise HTTPException(status_code=404, detail="Loan not found")
