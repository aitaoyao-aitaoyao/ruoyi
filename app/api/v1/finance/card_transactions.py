from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/card-transactions", tags=["finance-card-txns"])


@router.post("/", response_model=schemas.CreditCardTransactionRead, status_code=201)
def create_transaction(data: schemas.CreditCardTransactionCreate, db: Session = Depends(get_db)):
    return crud.create_card_transaction(db, data)


@router.get("/", response_model=list[schemas.CreditCardTransactionRead])
def list_transactions(card_id: int = Query(None), person_id: int = Query(None),
                      db: Session = Depends(get_db)):
    return crud.get_card_transactions(db, card_id, person_id)


@router.delete("/{txn_id}", status_code=204)
def delete_transaction(txn_id: int, db: Session = Depends(get_db)):
    if not crud.delete_card_transaction(db, txn_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
