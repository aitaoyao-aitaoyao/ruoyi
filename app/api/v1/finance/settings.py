"""设置接口 — 手头现金管理 + 应用设置"""
import shutil
from datetime import date, datetime
from pathlib import Path
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db import get_db
from app.auth import get_current_user
from app.models import User, AppSetting
from app import crud, schemas

router = APIRouter(prefix="/finance/settings", tags=["finance-settings"])


class SettingSet(BaseModel):
    key: str
    value: str


@router.get("/app/{key}")
def get_app_setting(key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.query(AppSetting).filter(AppSetting.key == key).first()
    return {"key": key, "value": s.value if s else ""}


@router.post("/app")
def set_app_setting(data: SettingSet, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.query(AppSetting).filter(AppSetting.key == data.key).first()
    if s:
        s.value = data.value
    else:
        s = AppSetting(key=data.key, value=data.value)
        db.add(s)
    db.commit()
    return {"key": data.key, "value": data.value}

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


@router.post("/backup")
def backup_database(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """备份 app.db 到 backups/ 目录"""
    db_path = Path("app.db")
    if not db_path.exists():
        return {"error": "app.db 不存在"}
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"app_{timestamp}.db"
    shutil.copy2(str(db_path), str(backup_path))
    # 只保留最近30个备份
    files = sorted(backup_dir.glob("app_*.db"), reverse=True)
    for f in files[30:]:
        f.unlink()
    return {"message": f"备份完成", "file": str(backup_path), "size": backup_path.stat().st_size}
