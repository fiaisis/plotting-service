"""
Main module
"""

import logging
import os
import sys
import typing
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, HTTPException
from h5grove.fastapi_utils import router, settings  # type: ignore
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from plotting_service.auth import get_experiments_for_user, get_user_from_token
from plotting_service.exceptions import AuthError
from plotting_service.utils import find_experiment_number, find_file

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
logger.info("Setting ceph directory to %s", CEPH_DIR)
settings.base_dir = Path(CEPH_DIR).resolve()
DEV_MODE = bool(os.environ.get("DEV_MODE", False))


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
    # we don't check experiment number as it is an int and pydantic wont process any non int type and return a 422
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

    path = find_file(CEPH_DIR, instrument, experiment_number, filename)
    if path is None:
        logger.error("Could not find the file requested.")
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST)

    with path.open("r") as file:
        return file.read()


@app.get("/find_file/instrument/{instrument}/experiment_number/{experiment_number}")
async def find_file_get(instrument: str, experiment_number: int, filename: str) -> str:
    """
    Return the relative path to the env var CEPH_DIR that leads to the requested file if one exists.
    :param instrument: Instrument the file belongs to.
    :param experiment_number: Experiment number the file belongs to.
    :param filename: Filename to find.
    :return: The relative path to the file in the CEPH_DIR env var.
    """
    path = find_file(CEPH_DIR, instrument, experiment_number, filename)
    if path is None:
        logger.error("Could not find the file requested.")
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST)
    # Remove CEPH_DIR
    if path.is_relative_to(CEPH_DIR):
        path = path.relative_to(CEPH_DIR)
    return str(path)


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
    experiment_number = find_experiment_number(request)

    auth_header = request.headers.get("Authorization")
    if auth_header is None:
        raise HTTPException(401, "Unauthenticated")

    token = auth_header.split(" ")[1]

    try:
        user = get_user_from_token(token)
    except AuthError:
        raise HTTPException(403, detail="Forbidden") from None
    logger.info("Checking role of user")
    if user.role == "staff":
        return await call_next(request)

    logger.info("Checking experiments for user")
    allowed_experiments = get_experiments_for_user(user)
    if experiment_number in allowed_experiments:
        return await call_next(request)

    raise HTTPException(403, detail="Forbidden")


app.include_router(router)
