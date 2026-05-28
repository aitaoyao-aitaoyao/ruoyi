from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth import get_current_user
from app.models import User
from app import crud, schemas

router = APIRouter(prefix="/finance/card-transactions", tags=["finance-card-txns"])


@router.post("/", response_model=schemas.CreditCardTransactionRead, status_code=201)
def create_transaction(data: schemas.CreditCardTransactionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.create_card_transaction(db, data)


@router.get("/", response_model=list[schemas.CreditCardTransactionRead])
def list_transactions(card_id: int = Query(None), person_id: int = Query(None),
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.get_card_transactions(db, card_id, person_id)


@router.patch("/{txn_id}", response_model=schemas.CreditCardTransactionRead)
def update_transaction(txn_id: int, data: schemas.CreditCardTransactionUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    txn = crud.update_card_transaction(db, txn_id, data)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@router.delete("/{txn_id}", status_code=204)
def delete_transaction(txn_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not crud.delete_card_transaction(db, txn_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
