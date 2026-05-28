from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth import get_current_user
from app.models import User
from app import crud, schemas
from app.finance.calc_engine import calc_installment_annual_rate

router = APIRouter(prefix="/finance/card-installments", tags=["finance-installments"])


def _compute_installment_fields(amount: float, periods: int, rate_type: str, rate_value: float) -> dict:
    """根据不同的费率输入方式，统一计算出分期各字段。"""
    if rate_type == "period_rate":
        period_rate = rate_value
    elif rate_type == "annual_rate":
        # 年化利率 → 每期费率（简化：annual_rate * (periods+1) / (24 * periods)）
        # 反推：annual_rate = period_rate * periods * 24 / (periods + 1)
        # → period_rate = annual_rate * (periods + 1) / (periods * 24)
        period_rate = rate_value * (periods + 1) / (periods * 24)
    elif rate_type == "total_fee":
        # 总手续费 → 每期费率 = total_fee / (amount * periods)
        period_rate = rate_value / (amount * periods)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown rate_type: {rate_type}")

    annual_rate = calc_installment_annual_rate(period_rate, periods)
    total_fee = round(amount * period_rate * periods, 2)
    period_principal = round(amount / periods, 2)
    period_fee = round(amount * period_rate, 2)
    return {
        "period_rate": round(period_rate, 6),
        "annual_rate": round(annual_rate, 4),
        "total_fee": total_fee,
        "period_principal": period_principal,
        "period_fee": period_fee,
        "period_total": round(period_principal + period_fee, 2),
    }


@router.post("/", response_model=schemas.CardInstallmentRead, status_code=201)
def create_installment(data: schemas.CardInstallmentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    calc_fields = _compute_installment_fields(
        amount=data.amount, periods=data.periods,
        rate_type=data.rate_type, rate_value=data.rate_value,
    )
    return crud.create_card_installment(db, data, calc_fields)


@router.get("/", response_model=list[schemas.CardInstallmentRead])
def list_installments(card_id: int = Query(None), person_id: int = Query(None),
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.get_card_installments(db, card_id, person_id)


@router.patch("/{inst_id}", response_model=schemas.CardInstallmentRead)
def update_installment(inst_id: int, data: schemas.CardInstallmentUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inst = crud.update_card_installment(db, inst_id, data)
    if not inst:
        raise HTTPException(status_code=404, detail="Installment not found")
    return inst


@router.patch("/{inst_id}/pay-period", response_model=schemas.CardInstallmentRead)
def pay_period(inst_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inst = crud.pay_installment_period(db, inst_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Installment not found")
    return inst


@router.delete("/{inst_id}", status_code=204)
def delete_installment(inst_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not crud.delete_card_installment(db, inst_id):
        raise HTTPException(status_code=404, detail="Installment not found")


@router.post("/batch-delete", status_code=200)
def batch_delete_installments(ids: list[int], db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    deleted = 0
    for iid in ids:
        if crud.delete_card_installment(db, iid):
            deleted += 1
    return {"deleted": deleted}
