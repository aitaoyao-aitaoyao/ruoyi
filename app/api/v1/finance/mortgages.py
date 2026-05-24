from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/mortgages", tags=["finance-mortgages"])


@router.post("/", response_model=schemas.MortgageRead, status_code=201)
def create_mortgage(data: schemas.MortgageCreate, db: Session = Depends(get_db)):
    return crud.create_mortgage(db, data)


@router.get("/", response_model=list[schemas.MortgageRead])
def list_mortgages(person_id: int = Query(None), db: Session = Depends(get_db)):
    return crud.get_mortgages(db, person_id)


@router.patch("/{mortgage_id}", response_model=schemas.MortgageRead)
def update_principal(mortgage_id: int, remaining_principal: float, db: Session = Depends(get_db)):
    m = crud.update_mortgage_principal(db, mortgage_id, remaining_principal)
    if not m:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    return m


@router.delete("/{mortgage_id}", status_code=204)
def delete_mortgage(mortgage_id: int, db: Session = Depends(get_db)):
    if not crud.delete_mortgage(db, mortgage_id):
        raise HTTPException(status_code=404, detail="Mortgage not found")
