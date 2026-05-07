from fastapi import APIRouter, Depends, HTTPException, status
from ..schemas import Token, LoginRequest
from ..services.keycloak_manager import keycloak_manager

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
async def login(request: LoginRequest):
    token = keycloak_manager.get_token(request.username, request.password)
    return {
        "access_token": token["access_token"],
        "refresh_token": token["refresh_token"],
        "expires_in": token["expires_in"],
        "refresh_expires_in": token["refresh_expires_in"]
    }

@router.post("/refresh", response_model=Token)
async def refresh(refresh_token: str):
    token = keycloak_manager.refresh_token(refresh_token)
    return {
        "access_token": token["access_token"],
        "refresh_token": token["refresh_token"],
        "expires_in": token["expires_in"],
        "refresh_expires_in": token["refresh_expires_in"]
    }

@router.post("/logout")
async def logout(refresh_token: str):
    keycloak_manager.logout(refresh_token)
    return {"message": "Successfully logged out"}
