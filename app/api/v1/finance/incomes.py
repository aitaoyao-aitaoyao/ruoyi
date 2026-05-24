from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/incomes", tags=["finance-incomes"])


@router.post("/", response_model=schemas.IncomeRead, status_code=201)
def create_income(data: schemas.IncomeCreate, db: Session = Depends(get_db)):
    return crud.create_income(db, data)


@router.get("/", response_model=list[schemas.IncomeRead])
def list_incomes(person_id: int = Query(None), period_value: str = Query(None),
                 db: Session = Depends(get_db)):
    return crud.get_incomes(db, person_id, period_value)


@router.delete("/{income_id}", status_code=204)
def delete_income(income_id: int, db: Session = Depends(get_db)):
    if not crud.delete_income(db, income_id):
        raise HTTPException(status_code=404, detail="Income not found")
