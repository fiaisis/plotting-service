"""
Main module
"""

import logging
import os
import sys
import typing
from http import HTTPStatus
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from h5grove.fastapi_utils import router, settings  # type: ignore
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from plotting_service.auth import get_experiments_for_user, get_user_from_token
from plotting_service.exceptions import AuthError
from plotting_service.utils import (
    find_experiment_number,
)

stdout_handler = logging.StreamHandler(stream=sys.stdout)
logging.basicConfig(
    handlers=[stdout_handler],
    format="[%(asctime)s]-%(name)s-%(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logger.info("Starting Plotting Service")

ALLOWED_ORIGINS = ["*"]
CEPH_DIR = os.environ.get("CEPH_DIR", "/ceph")
FIA_API_URL = os.environ.get("FIA_API_URL", "http://localhost:8001")
FIA_API_API_KEY = os.environ.get("FIA_API_API_KEY", "shh")
logger.info("Setting ceph directory to %s", CEPH_DIR)
settings.base_dir = Path(CEPH_DIR).resolve()
DEV_MODE = bool(os.environ.get("DEV_MODE", False))
if DEV_MODE:
    logger.info("Development only mode")
else:
    logger.info("Production ready mode")


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def get() -> typing.Literal["ok"]:
    """
    Health check endpoint
    \f
    :return: "ok"
    """
    return "ok"


@app.get("/text/instrument/{instrument}/experiment_number/{experiment_number}", response_class=PlainTextResponse)
async def get_text_file(instrument: str, experiment_number: int, filename: str) -> str:
    # We don't check experiment number as it is an int and pydantic won't process any non int type and return a 422
    # automatically
    if (
        ".." in instrument
        or ".." in filename
        or "/" in instrument
        or "/" in filename
        or "\\" in instrument
        or "\\" in filename
        or "~" in instrument
        or "~" in filename
    ):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN)

    path = Path(
        requests.get(
            f"{FIA_API_URL}/find_file/instrument/{instrument}/experiment_number/{experiment_number}?filename={filename}",
            headers={"Authorization": f"Bearer {FIA_API_API_KEY}"},
            timeout=30,
        ).text
    )

    # Returned path is relative to CEPH_DIR (prepending to generate absolute path)
    # stripping extra quotes to prevent FileNotFound
    path = Path(CEPH_DIR) / Path(str(path).strip('"'))

    if path is None:
        logger.error("Could not find the file requested.")
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST)

    # UnicodeDecodeError: 'utf-8' codec can't decode byte, invalid start byte
    with path.open("r") as file:
        return file.read()


@app.middleware("http")
async def check_permissions(request: Request, call_next: typing.Callable[..., typing.Any]) -> typing.Any:
    """
    Middleware that checks the requestee token has permissions for that experiment
    :param request: The request to check
    :param call_next: The next call (the route function called)
    :return: A response
    """
    if DEV_MODE:
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path in ("/healthz", "/docs"):
        return await call_next(request)

    logger.info(f"Checking permissions for {request.url.path}")

    auth_header = request.headers.get("Authorization")
    if auth_header is None:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Unauthenticated")

    token = auth_header.split(" ")[1]

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


app.include_router(router)
