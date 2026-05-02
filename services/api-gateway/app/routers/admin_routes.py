from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from httpx import HTTPStatusError

from app.services.route_client import add_route, update_route, delete_route
from app.schemas import RouteImportResponse, RouteDeleteResponse

router = APIRouter(
    prefix="/api/v1/admin/routes",
    tags=["Admin Routes"]
)

@router.post("/add-route", response_model=RouteImportResponse)
async def create_route(
    route_name: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Import a new route from an uploaded KML file.

    The uploaded KML must contain a LineString for the route path and at least
    two Point placemarks for stops. If a route with the same name already
    exists, it is replaced before the new route and stops are saved.
    """
    try:
        file_bytes = await file.read()
        return await add_route(route_name, file.filename, file_bytes, file.content_type)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@router.put("/{route_id}", response_model=RouteImportResponse)
async def replace_route(
    route_id: str,
    route_name: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Replace an existing route with data from a new KML upload.

    The uploaded KML is validated before the existing route and stops are
    replaced. Returns 404 when the route ID does not exist.
    """
    try:
        file_bytes = await file.read()
        return await update_route(route_id, route_name, file.filename, file_bytes, file.content_type)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@router.delete("/{route_id}", response_model=RouteDeleteResponse)
async def remove_route(route_id: str):
    """
    Delete a route and its related stops.

    Removes the route identified by `route_id`. Related stops are removed automatically.
    Returns 404 when the route ID does not exist.
    """
    try:
        return await delete_route(route_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
