from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth import get_current_user
from app.models import User
from app import crud, schemas

router = APIRouter(prefix="/finance/expenses", tags=["finance-expenses"])


@router.post("/", response_model=schemas.ExpenseRead, status_code=201)
def create_expense(data: schemas.ExpenseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.create_expense(db, data)


@router.get("/", response_model=list[schemas.ExpenseRead])
def list_expenses(person_id: int = Query(None), period_value: str = Query(None),
                  category: str = Query(None), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.get_expenses(db, person_id, period_value, category)


@router.get("/{expense_id}", response_model=schemas.ExpenseRead)
def get_expense(expense_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    exp = crud.get_expense(db, expense_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    return exp


@router.patch("/{expense_id}", response_model=schemas.ExpenseRead)
def update_expense(expense_id: int, data: schemas.ExpenseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    exp = crud.update_expense(db, expense_id, data)
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    return exp


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not crud.delete_expense(db, expense_id):
        raise HTTPException(status_code=404, detail="Expense not found")
