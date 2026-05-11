from fastapi import APIRouter, Request, HTTPException
import httpx
import os

router = APIRouter(prefix="/auth", tags=["Auth Proxy"])

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8005")

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_auth(request: Request, path: str):
    async with httpx.AsyncClient() as client:
        url = f"{AUTH_SERVICE_URL}/auth/{path}"
        method = request.method
        content = await request.body()
        headers = dict(request.headers)
        # Remove host header to avoid issues with the target service
        headers.pop("host", None)
        
        try:
            response = await client.request(
                method, url, content=content, headers=headers, params=request.query_params
            )
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error connecting to Auth Service: {str(e)}")
