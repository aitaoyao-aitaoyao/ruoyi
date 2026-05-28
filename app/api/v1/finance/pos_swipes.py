from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth import get_current_user
from app.models import User
from app import crud, schemas
from app.finance.calc_engine import calc_pos_fee

router = APIRouter(prefix="/finance/pos-swipes", tags=["finance-pos"])


@router.post("/", response_model=schemas.PosSwipeRead, status_code=201)
def create_pos_swipe(data: schemas.PosSwipeCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if data.fee_rate is None:
        config = crud.get_active_fee_config(db, "pos_swipe")
        fee_rate = config.rate if config else 0.006
    else:
        fee_rate = data.fee_rate
    fee = calc_pos_fee(data.amount, fee_rate)
    data.fee_rate = fee_rate
    return crud.create_pos_swipe(db, data, fee)


@router.get("/", response_model=list[schemas.PosSwipeRead])
def list_pos_swipes(person_id: int = Query(None), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.get_pos_swipes(db, person_id)


@router.get("/{swipe_id}", response_model=schemas.PosSwipeRead)
def get_pos_swipe(swipe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    swipe = crud.get_pos_swipe(db, swipe_id)
    if not swipe:
        raise HTTPException(status_code=404, detail="POS swipe not found")
    return swipe


@router.patch("/{swipe_id}", response_model=schemas.PosSwipeRead)
def update_pos_swipe(swipe_id: int, data: schemas.PosSwipeUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.finance.calc_engine import calc_pos_fee
    existing = crud.get_pos_swipe(db, swipe_id)
    if not existing:
        raise HTTPException(status_code=404, detail="POS swipe not found")

    # 如果金额或费率变了，重新计算手续费
    new_amount = data.amount if data.amount is not None else existing.amount
    new_fee_rate = data.fee_rate if data.fee_rate is not None else existing.fee_rate
    if data.amount is not None or data.fee_rate is not None:
        swipe = crud.update_pos_swipe(db, swipe_id, data, recalc_fee=True)
    else:
        swipe = crud.update_pos_swipe(db, swipe_id, data)
    if not swipe:
        raise HTTPException(status_code=404, detail="POS swipe not found")
    return swipe


@router.delete("/{swipe_id}", status_code=204)
def delete_pos_swipe(swipe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not crud.delete_pos_swipe(db, swipe_id):
        raise HTTPException(status_code=404, detail="POS swipe not found")
