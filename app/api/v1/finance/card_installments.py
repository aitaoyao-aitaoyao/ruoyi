from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas
from app.finance.calc_engine import calc_installment_annual_rate

router = APIRouter(prefix="/finance/card-installments", tags=["finance-installments"])


@router.post("/", response_model=schemas.CardInstallmentRead, status_code=201)
def create_installment(data: schemas.CardInstallmentCreate, db: Session = Depends(get_db)):
    annual_rate = calc_installment_annual_rate(data.period_rate, data.periods)
    total_fee = round(data.amount * data.period_rate * data.periods, 2)
    period_principal = round(data.amount / data.periods, 2)
    period_fee = round(data.amount * data.period_rate, 2)
    calc_fields = {
        "annual_rate": round(annual_rate, 4),
        "total_fee": total_fee,
        "period_principal": period_principal,
        "period_fee": period_fee,
        "period_total": round(period_principal + period_fee, 2),
    }
    return crud.create_card_installment(db, data, calc_fields)


@router.get("/", response_model=list[schemas.CardInstallmentRead])
def list_installments(card_id: int = Query(None), person_id: int = Query(None),
                      db: Session = Depends(get_db)):
    return crud.get_card_installments(db, card_id, person_id)


@router.patch("/{inst_id}/pay-period", response_model=schemas.CardInstallmentRead)
def pay_period(inst_id: int, db: Session = Depends(get_db)):
    inst = crud.pay_installment_period(db, inst_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Installment not found")
    return inst


@router.delete("/{inst_id}", status_code=204)
def delete_installment(inst_id: int, db: Session = Depends(get_db)):
    if not crud.delete_card_installment(db, inst_id):
        raise HTTPException(status_code=404, detail="Installment not found")
