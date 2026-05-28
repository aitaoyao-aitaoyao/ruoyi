"""回收站 API — 查看、恢复、永久删除已删除的记录。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth import get_current_user, require_role
from app.models import User
from app import crud

router = APIRouter(prefix="/finance/recycle-bin", tags=["finance-recycle-bin"])


@router.get("/")
def list_deleted(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    records = crud.get_deleted_records(db)
    import json
    result = []
    for r in records:
        try:
            preview = json.loads(r.record_data)
        except Exception:
            preview = {}
        result.append({
            "id": r.id,
            "table_name": r.table_name,
            "record_id": r.record_id,
            "deleted_at": r.deleted_at.isoformat() if r.deleted_at else None,
            "preview": str(preview),
        })
    return result


@router.post("/{deleted_id}/restore")
def restore(deleted_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    dr = crud.restore_record(db, deleted_id)
    if not dr:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"message": f"Record restored to {dr.table_name}"}


@router.delete("/{deleted_id}", status_code=204)
def permanent_delete(deleted_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not crud.permanently_delete_record(db, deleted_id):
        raise HTTPException(status_code=404, detail="Record not found")


@router.delete("/clear", status_code=200)
def clear_all(db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    count = crud.clear_deleted_records(db)
    return {"message": f"{count} records permanently deleted"}
