from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth import get_current_user
from app.models import User
from app import crud, schemas

router = APIRouter(prefix="/finance/platforms", tags=["finance-platforms"])


@router.post("/", response_model=schemas.LoanPlatformRead, status_code=201)
def create_platform(data: schemas.LoanPlatformCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.create_platform(db, data)


@router.get("/", response_model=list[schemas.LoanPlatformRead])
def list_platforms(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.get_platforms(db)


@router.get("/{platform_id}", response_model=schemas.LoanPlatformRead)
def get_platform(platform_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    platform = crud.get_platform(db, platform_id)
    if not platform:
        raise HTTPException(status_code=404, detail="Platform not found")
    return platform


@router.patch("/{platform_id}", response_model=schemas.LoanPlatformRead)
def update_platform(platform_id: int, data: schemas.LoanPlatformUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    platform = crud.update_platform(db, platform_id, data)
    if not platform:
        raise HTTPException(status_code=404, detail="Platform not found")
    return platform


@router.delete("/{platform_id}", status_code=204)
def delete_platform(platform_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not crud.delete_platform(db, platform_id):
        raise HTTPException(status_code=404, detail="Platform not found")
