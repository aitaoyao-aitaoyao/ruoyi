"""设置接口 — 手头现金管理"""
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth import get_current_user
from app.models import User
from app import crud, schemas

router = APIRouter(prefix="/finance/settings", tags=["finance-settings"])


@router.post("/cash", response_model=schemas.CashRecordRead)
def add_cash(data: schemas.CashRecordCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """录入当前手头现金余额"""
    return crud.create_cash_record(db, data, recorded_at=data.recorded_at or date.today())


@router.get("/cash/latest")
def get_latest_cash(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """获取最近一次录入的手头现金"""
    rec = crud.get_latest_cash(db)
    if rec:
        return schemas.CashRecordRead.model_validate(rec)
    return {"amount": 0, "recorded_at": None, "note": "未录入", "id": 0}


@router.get("/cash/history", response_model=list[schemas.CashRecordRead])
def get_cash_history(limit: int = Query(24, ge=1, le=60), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """获取手头现金历史记录"""
    return crud.get_cash_records(db, limit=limit)
