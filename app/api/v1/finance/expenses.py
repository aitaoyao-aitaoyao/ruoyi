from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/expenses", tags=["finance-expenses"])


@router.post("/", response_model=schemas.ExpenseRead, status_code=201)
def create_expense(data: schemas.ExpenseCreate, db: Session = Depends(get_db)):
    return crud.create_expense(db, data)


@router.get("/", response_model=list[schemas.ExpenseRead])
def list_expenses(person_id: int = Query(None), period_value: str = Query(None),
                  category: str = Query(None), db: Session = Depends(get_db)):
    return crud.get_expenses(db, person_id, period_value, category)


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    if not crud.delete_expense(db, expense_id):
        raise HTTPException(status_code=404, detail="Expense not found")
