"""Main module."""

import logging
import os
import sys
import typing
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from starlette.middleware.gzip import GZipMiddleware
from PIL import Image
from h5grove.fastapi_utils import router, settings  # type: ignore
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from plotting_service.auth import get_experiments_for_user, get_user_from_token
from plotting_service.exceptions import AuthError
from plotting_service.routers.health import HealthRouter
from plotting_service.routers.imat import ImatRouter
from plotting_service.routers.live_data import LiveDataRouter
from plotting_service.routers.plotting import PlottingRouter
from plotting_service.utils import (
    find_experiment_number,
    get_current_rb_async,
)

stdout_handler = logging.StreamHandler(stream=sys.stdout)
logging.basicConfig(
    handlers=[stdout_handler],
    format="[%(asctime)s]-%(name)s-%(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logger.info("Starting Plotting Service")

DEV_MODE = os.environ.get("DEV_MODE", "False").lower() == "true"
if DEV_MODE:
    logger.info("Development only mode")
else:
    logger.info("Production ready mode")
app = FastAPI()

ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

CEPH_DIR = os.environ.get("CEPH_DIR", "/ceph")
logger.info("Setting ceph directory to %s", CEPH_DIR)
settings.base_dir = Path(CEPH_DIR).resolve()


@app.middleware("http")
async def check_permissions(request: Request, call_next: typing.Callable[..., typing.Any]) -> typing.Any:  # noqa: C901, PLR0911
    """Middleware that checks the requestee token has permissions for that
    experiment
    :param request: The request to check
    :param call_next: The next call (the route function called)
    :return: A response.
    """
    if DEV_MODE:
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path.startswith(("/live", "/healthz", "/docs")):
        return await call_next(request)

    logger.info(f"Checking permissions for {request.url.path}")

    auth_header = request.headers.get("Authorization")
    if auth_header is None:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Unauthenticated")

    token = auth_header.split(" ")[1]

    api_key = os.environ.get("API_KEY", "")
    if token == api_key and api_key != "":
        return await call_next(request)

    try:
        user = get_user_from_token(token)
    except AuthError:
        raise HTTPException(HTTPStatus.FORBIDDEN, detail="Forbidden") from None
    logger.info("Checking role of user")
    if user.role == "staff":
        # Bypass permission check
        return await call_next(request)

    # Handle case without experiment number
    if request.url.path.startswith("/find_file/generic/user_number/"):
        # Does not have an experiment number! Extract user number and check based on that.
        user_number = request.path_params["user_number"]
        if user_number == user.user_number:
            return await call_next(request)
        raise HTTPException(HTTPStatus.FORBIDDEN, detail="Forbidden")

    # Otherwise handle with experiment number
    experiment_number = find_experiment_number(request)

    logger.info("Checking experiments for user")
    allowed_experiments = get_experiments_for_user(user)
    if experiment_number in allowed_experiments:
        return await call_next(request)

    raise HTTPException(HTTPStatus.FORBIDDEN, detail="Forbidden")


@app.middleware("http")
async def check_live_permissions(request: Request, call_next: typing.Callable[..., typing.Any]) -> typing.Any:  # noqa: C901, PLR0911, PLR0912
    """
    Middleware for the live app that checks if the user has permission
    to view the *current* experiment on the requested instrument.
    """
    if DEV_MODE:
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path in ("/healthz", "/docs", "/openapi.json"):
        return await call_next(request)

    logger.info(f"Checking live permissions for {request.url.path}")

    token_query = request.query_params.get("token")
    if token_query is None:
        token_query = request.headers.get("Authorization")
        if token_query is not None:
            token_query = token_query.split(" ")[1]
    if token_query is None:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Unauthenticated")

    token = token_query

    # API Key check (if applicable globally, otherwise remove/adapt)
    api_key = os.environ.get("API_KEY", "")
    if token == api_key and api_key != "":
        return await call_next(request)

    try:
        user = get_user_from_token(token)
    except AuthError:
        raise HTTPException(HTTPStatus.FORBIDDEN, detail="Forbidden") from None

    if user.role == "staff":
        return await call_next(request)

    file_param = request.query_params.get("file")
    if not file_param:
        logger.warning(f"Request to live app without 'file' param: {request.url}")

        if request.url.path == "/":  # Root of sub-app
            return await call_next(request)
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Missing 'file' parameter for live check")

    # Assuming structure: INSTRUMENT/RBnumber/...
    parts = Path(file_param).parts
    if not parts or parts[0] == "/" or parts[0] == ".":
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid file path format")

    instrument = parts[0]

    try:
        current_rb = await get_current_rb_async(instrument)
    except Exception as e:
        logger.error(f"Failed to get current RB for instrument {instrument}: {e}")
        # If we can't check 'live' status, fail safe
        raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to verify live experiment status") from None

    try:
        # It usually comes as just the number from the PV, but handle "RB" prefix just in case
        current_rb_int = int(current_rb[2:]) if current_rb.upper().startswith("RB") else int(current_rb)
    except ValueError:
        logger.error(f"Invalid RB number format from PV: {current_rb}")
        raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "Invalid live experiment data") from None

    logger.info(f"Checking if user {user.user_number} has access to current RB {current_rb_int} on {instrument}")
    allowed_experiments = get_experiments_for_user(user)

    if current_rb_int in allowed_experiments:
        return await call_next(request)

    logger.warning(f"User {user.user_number} denied access to live experiment {current_rb_int}")
    raise HTTPException(HTTPStatus.FORBIDDEN, detail="Forbidden: You do not have access to the current live experiment")

@app.get("/imat/list-images", summary="List images in a directory")
async def list_imat_images(
    path: str = Query(..., description="Path to the directory containing images, relative to CEPH_DIR")
) -> list[str]:
    """Return a sorted list of TIFF images in the given directory."""
    from plotting_service.utils import safe_check_filepath
    
    dir_path = (Path(CEPH_DIR) / path).resolve()
    # Security: Ensure path is within CEPH_DIR
    safe_check_filepath(dir_path, CEPH_DIR)

    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Directory not found")

    images = []
    for entry in dir_path.iterdir():
        if entry.is_file() and entry.suffix.lower() in IMAGE_SUFFIXES:
            images.append(entry.name)

    return sorted(images)


@app.get("/imat/image", summary="Fetch a specific TIFF image as raw data")
async def get_imat_image(
    path: str = Query(..., description="Path to the TIFF image file, relative to CEPH_DIR"),
    downsample_factor: typing.Annotated[
        int,
        Query(
            ge=1,
            le=64,
            description="Integer factor to reduce each dimension by (1 keeps original resolution).",
        ),
    ] = 1,
) -> Response:
    """Return the raw data of a specific TIFF image as binary."""
    from plotting_service.utils import safe_check_filepath
    
    image_path = (Path(CEPH_DIR) / path).resolve()
    # Security: Ensure path is within CEPH_DIR
    safe_check_filepath(image_path, CEPH_DIR)

    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Image not found")

    try:
        with Image.open(image_path) as img:
            original_width, original_height = img.size

            if downsample_factor > 1:
                target_width = max(1, round(original_width / downsample_factor))
                target_height = max(1, round(original_height / downsample_factor))
                img = img.resize((target_width, target_height), Image.Resampling.NEAREST)

            sampled_width, sampled_height = img.size
            # For 16-bit TIFFs, tobytes() returns raw 16-bit bytes
            data_bytes = img.tobytes()

        headers = {
            "X-Image-Width": str(sampled_width),
            "X-Image-Height": str(sampled_height),
            "X-Original-Width": str(original_width),
            "X-Original-Height": str(original_height),
            "X-Downsample-Factor": str(downsample_factor),
            "Access-Control-Expose-Headers": "X-Image-Width, X-Image-Height, X-Original-Width, X-Original-Height, X-Downsample-Factor"
        }
        
        return Response(
            content=data_bytes,
            media_type="application/octet-stream",
            headers=headers
        )

    except Exception as exc:
        logger.error(f"Failed to process image {image_path}: {exc}")
        raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to process image") from exc


app.include_router(router)
app.include_router(HealthRouter)
app.include_router(PlottingRouter)
app.include_router(ImatRouter)
app.include_router(LiveDataRouter)
