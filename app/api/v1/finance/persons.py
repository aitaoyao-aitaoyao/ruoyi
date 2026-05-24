from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/persons", tags=["finance-persons"])


@router.post("/", response_model=schemas.PersonRead, status_code=201)
def create_person(data: schemas.PersonCreate, db: Session = Depends(get_db)):
    return crud.create_person(db, data)


@router.get("/", response_model=list[schemas.PersonRead])
def list_persons(db: Session = Depends(get_db)):
    return crud.get_persons(db)


@router.get("/{person_id}", response_model=schemas.PersonRead)
def get_person(person_id: int, db: Session = Depends(get_db)):
    person = crud.get_person(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.delete("/{person_id}", status_code=204)
def delete_person(person_id: int, db: Session = Depends(get_db)):
    if not crud.delete_person(db, person_id):
        raise HTTPException(status_code=404, detail="Person not found")
