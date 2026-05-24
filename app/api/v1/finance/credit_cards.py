from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/credit-cards", tags=["finance-cards"])


@router.post("/", response_model=schemas.CreditCardRead, status_code=201)
def create_card(data: schemas.CreditCardCreate, db: Session = Depends(get_db)):
    return crud.create_credit_card(db, data)


@router.get("/", response_model=list[schemas.CreditCardRead])
def list_cards(person_id: int = Query(None), db: Session = Depends(get_db)):
    return crud.get_credit_cards(db, person_id)


@router.get("/{card_id}", response_model=schemas.CreditCardRead)
def get_card(card_id: int, db: Session = Depends(get_db)):
    card = crud.get_credit_card(db, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    return card


@router.patch("/{card_id}", response_model=schemas.CreditCardRead)
def update_card(card_id: int, data: schemas.CreditCardUpdate, db: Session = Depends(get_db)):
    card = crud.update_credit_card(db, card_id, data)
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    return card


@router.delete("/{card_id}", status_code=204)
def delete_card(card_id: int, db: Session = Depends(get_db)):
    if not crud.delete_credit_card(db, card_id):
        raise HTTPException(status_code=404, detail="Credit card not found")
