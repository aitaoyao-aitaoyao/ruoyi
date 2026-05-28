from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth import get_current_user, require_role
from app.models import User
from app import crud, schemas

router = APIRouter(prefix="/finance/fee-configs", tags=["finance-fee-configs"])


@router.post("/", response_model=schemas.FeeConfigRead, status_code=201)
def create_fee_config(data: schemas.FeeConfigCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.create_fee_config(db, data)


@router.get("/", response_model=list[schemas.FeeConfigRead])
def list_fee_configs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.get_fee_configs(db)


@router.get("/{config_id}", response_model=schemas.FeeConfigRead)
def get_fee_config(config_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    fc = crud.get_fee_config(db, config_id)
    if not fc:
        raise HTTPException(status_code=404, detail="Fee config not found")
    return fc


@router.patch("/{config_id}", response_model=schemas.FeeConfigRead)
def update_fee_config(config_id: int, data: schemas.FeeConfigCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    fc = crud.update_fee_config(db, config_id, data)
    if not fc:
        raise HTTPException(status_code=404, detail="Fee config not found")
    return fc


@router.delete("/admin/clear-all", status_code=200)
def clear_all_finance_data(db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    """清空所有财务数据（保留人员信息）"""
    counts = crud.clear_all_finance_data(db)
    return {"message": "所有财务数据已清空", "deleted": counts}


@router.delete("/{config_id}", status_code=204)
def delete_fee_config(config_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not crud.delete_fee_config(db, config_id):
        raise HTTPException(status_code=404, detail="Fee config not found")
