from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.auth import get_current_user
from app.models import User
from app.finance.calc_engine import (
    calc_equal_installment_plan, calc_interest_first_plan, calc_bullet_plan,
    calc_installment_annual_rate, convert_to_monthly_rate,
)

router = APIRouter(prefix="/finance/calc", tags=["finance-calc"])


class InterestCalcRequest(BaseModel):
    amount: float
    rate: float
    rate_type: str
    periods: int
    method: str
    start_date: str = "2000-01-01"


@router.post("/interest")
def calc_interest(data: InterestCalcRequest, user: User = Depends(get_current_user)):
    monthly_rate = convert_to_monthly_rate(data.rate, data.rate_type)
    if data.method == "equal_installment":
        plan = calc_equal_installment_plan(data.amount, monthly_rate, data.periods, data.start_date)
    elif data.method == "interest_first":
        plan = calc_interest_first_plan(data.amount, monthly_rate, data.periods, data.start_date)
    else:
        plan = calc_bullet_plan(data.amount, monthly_rate, data.periods, data.start_date)
    total_interest = sum(p["interest"] for p in plan)
    return {"monthly_rate": monthly_rate, "plan": plan, "total_interest": total_interest}


class AnnualRateRequest(BaseModel):
    period_rate: float
    periods: int


@router.post("/annual-rate")
def calc_annual_rate(data: AnnualRateRequest, user: User = Depends(get_current_user)):
    return {"annual_rate": calc_installment_annual_rate(data.period_rate, data.periods)}
