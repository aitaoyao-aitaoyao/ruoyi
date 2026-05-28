from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth import get_current_user
from app.models import User
from app import crud, schemas

router = APIRouter(prefix="/finance/incomes", tags=["finance-incomes"])


@router.post("/", response_model=schemas.IncomeRead, status_code=201)
def create_income(data: schemas.IncomeCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.create_income(db, data)


@router.get("/", response_model=list[schemas.IncomeRead])
def list_incomes(person_id: int = Query(None), period_value: str = Query(None),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.get_incomes(db, person_id, period_value)


@router.get("/{income_id}", response_model=schemas.IncomeRead)
def get_income(income_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inc = crud.get_income(db, income_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Income not found")
    return inc


@router.patch("/{income_id}", response_model=schemas.IncomeRead)
def update_income(income_id: int, data: schemas.IncomeUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inc = crud.update_income(db, income_id, data)
    if not inc:
        raise HTTPException(status_code=404, detail="Income not found")
    return inc


@router.delete("/{income_id}", status_code=204)
def delete_income(income_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not crud.delete_income(db, income_id):
        raise HTTPException(status_code=404, detail="Income not found")
