from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ...db import get_db
from ... import crud, schemas

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=schemas.CategoriesListResponse)
def get_categories(db: Session = Depends(get_db)):
    return {"items": crud.list_categories(db)}


@router.post("", response_model=schemas.CategoryOut, status_code=status.HTTP_201_CREATED)
def post_category(data: schemas.CategoryCreate, db: Session = Depends(get_db)):
    return crud.create_category(db, data)


@router.get("/{category_id}", response_model=schemas.CategoryOut)
def get_category(category_id: int, db: Session = Depends(get_db)):
    obj = crud.get_category(db, category_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Category not found")
    return obj


@router.put("/{category_id}", response_model=schemas.CategoryOut)
def put_category(category_id: int, data: schemas.CategoryUpdate, db: Session = Depends(get_db)):
    try:
        return crud.update_category(db, category_id, data)
    except ValueError:
        raise HTTPException(status_code=404, detail="Category not found")


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    crud.delete_category(db, category_id)
