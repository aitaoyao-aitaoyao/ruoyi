from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from dateutil.relativedelta import relativedelta
from app.db import get_db
from app.auth import get_current_user
from app.models import User
from app import crud, schemas

router = APIRouter(prefix="/finance/mortgages", tags=["finance-mortgages"])


@router.post("/", response_model=schemas.MortgageRead, status_code=201)
def create_mortgage(data: schemas.MortgageCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not data.end_date:
        data.end_date = data.start_date + relativedelta(months=data.total_periods)
    return crud.create_mortgage(db, data)


@router.get("/", response_model=list[schemas.MortgageRead])
def list_mortgages(person_id: int = Query(None), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.get_mortgages(db, person_id)


@router.patch("/{mortgage_id}", response_model=schemas.MortgageRead)
def update_mortgage(mortgage_id: int, data: schemas.MortgageUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = crud.update_mortgage(db, mortgage_id, data)
    if not m:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    return m


@router.delete("/{mortgage_id}", status_code=204)
def delete_mortgage(mortgage_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not crud.delete_mortgage(db, mortgage_id):
        raise HTTPException(status_code=404, detail="Mortgage not found")
