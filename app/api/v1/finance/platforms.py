from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/platforms", tags=["finance-platforms"])


@router.post("/", response_model=schemas.LoanPlatformRead, status_code=201)
def create_platform(data: schemas.LoanPlatformCreate, db: Session = Depends(get_db)):
    return crud.create_platform(db, data)


@router.get("/", response_model=list[schemas.LoanPlatformRead])
def list_platforms(db: Session = Depends(get_db)):
    return crud.get_platforms(db)


@router.delete("/{platform_id}", status_code=204)
def delete_platform(platform_id: int, db: Session = Depends(get_db)):
    if not crud.delete_platform(db, platform_id):
        raise HTTPException(status_code=404, detail="Platform not found")
