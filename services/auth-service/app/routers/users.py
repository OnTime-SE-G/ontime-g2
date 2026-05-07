from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..services.keycloak_manager import keycloak_manager

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
    db.commit()
    db.refresh(db_user)
    
    return db_user

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
