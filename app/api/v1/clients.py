from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("/", response_model=List[schemas.ClientResponse])
def get_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return crud.get_clients(db=db, skip=skip, limit=limit)


@router.get("/{client_id}", response_model=schemas.ClientResponse)
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = crud.get_client(db, client_id)

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return client


@router.post(
    "/",
    response_model=schemas.ClientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_client(client: schemas.ClientCreate, db: Session = Depends(get_db)):

    existing_client = crud.get_client_by_name(db, client.name)

    if existing_client:
        raise HTTPException(
            status_code=400,
            detail="A client with this name already exists."
        )

    return crud.create_client(db, client)


@router.put("/{client_id}", response_model=schemas.ClientResponse)
def update_client(
    client_id: int,
    client: schemas.ClientUpdate,
    db: Session = Depends(get_db),
):
    updated = crud.update_client(db, client_id, client)

    if not updated:
        raise HTTPException(status_code=404, detail="Client not found")

    return updated


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_client(db, client_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Client not found")

    return None

# ---------- Client Locations ----------


@router.get(
    "/{client_id}/locations",
    response_model=schemas.ClientLocationsListResponse,
)
def get_client_locations(
    client_id: int,
    db: Session = Depends(get_db),
):
    client = crud.get_client(db, client_id)

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    locations = crud.get_client_locations(db=db, client_id=client_id)

    return {"items": locations}


@router.post(
    "/{client_id}/locations",
    response_model=schemas.ClientLocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_client_location(
    client_id: int,
    location: schemas.ClientLocationCreate,
    db: Session = Depends(get_db),
):
    try:
        return crud.create_client_location(
            db=db,
            client_id=client_id,
            location_in=location,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/locations/{location_id}",
    response_model=schemas.ClientLocationResponse,
)
def update_client_location(
    location_id: int,
    location: schemas.ClientLocationUpdate,
    db: Session = Depends(get_db),
):
    updated = crud.update_client_location(
        db=db,
        location_id=location_id,
        location_in=location,
    )

    if not updated:
        raise HTTPException(
            status_code=404, detail="Client location not found")

    return updated


@router.delete(
    "/locations/{location_id}",
    response_model=schemas.ClientLocationResponse,
)
def delete_client_location(
    location_id: int,
    db: Session = Depends(get_db),
):
    deleted = crud.delete_client_location(
        db=db,
        location_id=location_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404, detail="Client location not found")

    return deleted
