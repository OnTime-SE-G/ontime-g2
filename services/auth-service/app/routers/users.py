from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .. import models, schemas
from ..database import get_db
from ..services.keycloak_manager import keycloak_manager
from ..services.kafka_producer import kafka_service

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/register", response_model=schemas.UserOut)
async def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    # 1. Create user in Keycloak
    keycloak_id = keycloak_manager.create_user(user_in)
    
    # 2. Create user in local DB
    db_user = models.User(
        id=keycloak_id,
        email=user_in.email,
        username=user_in.username,
        first_name=user_in.first_name,
        last_name=user_in.last_name
    )
    db.add(db_user)

    if user_in.role == "DRIVER":
        if not user_in.license_number:
            # Note: in real app you might want to rollback keycloak user here
            raise HTTPException(status_code=400, detail="license_number is required for DRIVER role")
        db_driver = models.DriverProfile(
            user_id=keycloak_id,
            license_number=user_in.license_number,
            phone=user_in.phone
        )
        db.add(db_driver)

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # Note: Rollback keycloak user
        raise HTTPException(status_code=400, detail=f"Database error: {e}")

    db.refresh(db_user)

    # 3. Publish Event
    payload = {
        "id": keycloak_id,
        "email": user_in.email,
        "name": f"{user_in.first_name or ''} {user_in.last_name or ''}".strip(),
        "role": user_in.role
    }
    await kafka_service.publish_event("user-events", "USER_CREATED", payload)

    return db_user

@router.get("/drivers", response_model=list[schemas.DriverOut])
async def get_drivers(db: Session = Depends(get_db)):
    drivers = db.query(models.User).join(models.DriverProfile).all()
    # map User + DriverProfile to DriverOut
    res = []
    for user in drivers:
        res.append({
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "license_number": user.driver_profile.license_number,
            "phone": user.driver_profile.phone
        })
    return res

@router.get("/me", response_model=schemas.UserOut)
async def get_me(db: Session = Depends(get_db)):
    # Note: In a real scenario, we would get the user ID from the JWT token
    # For now, this is a placeholder
    raise HTTPException(status_code=501, detail="Not implemented - JWT validation required")

@router.get("/{user_id}", response_model=schemas.UserOut)
async def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
