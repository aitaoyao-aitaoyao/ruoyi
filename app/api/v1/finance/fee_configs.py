from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/fee-configs", tags=["finance-fee-configs"])


@router.post("/", response_model=schemas.FeeConfigRead, status_code=201)
def create_fee_config(data: schemas.FeeConfigCreate, db: Session = Depends(get_db)):
    return crud.create_fee_config(db, data)


@router.get("/", response_model=list[schemas.FeeConfigRead])
def list_fee_configs(db: Session = Depends(get_db)):
    return crud.get_fee_configs(db)


@router.delete("/{config_id}", status_code=204)
def delete_fee_config(config_id: int, db: Session = Depends(get_db)):
    if not crud.delete_fee_config(db, config_id):
        raise HTTPException(status_code=404, detail="Fee config not found")
