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
from plotting_service.utils import (
    find_experiment_number,
    find_file_experiment_number,
    find_file_instrument,
    find_file_user_number,
    request_path_check,
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
    try:
        with Path("/ceph/GENERIC/autoreduce/healthy_file.txt").open("r") as fle:
            lines = fle.readlines()
            if lines[0] != "This is a healthy file! You have read it correctly!":
                raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE)
        return "ok"
    except: #noqa: E722
        raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE) from None


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

    path = find_file_instrument(CEPH_DIR, instrument, experiment_number, filename)
    if path is None:
        logger.error("Could not find the file requested.")
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST)

    with path.open("r") as file:
        return file.read()


@app.get("/find_file/instrument/{instrument}/experiment_number/{experiment_number}")
async def find_file_get_instrument(instrument: str, experiment_number: int, filename: str) -> str:
    """
    Return the relative path to the env var CEPH_DIR that leads to the requested file if one exists.
    :param instrument: Instrument the file belongs to.
    :param experiment_number: Experiment number the file belongs to.
    :param filename: Filename to find.
    :return: The relative path to the file in the CEPH_DIR env var.
    """
    path = find_file_instrument(
        ceph_dir=CEPH_DIR, instrument=instrument, experiment_number=experiment_number, filename=filename
    )
    if path is None:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST)
    return str(request_path_check(path=path, base_dir=CEPH_DIR))


@app.get("/find_file/generic/experiment_number/{experiment_number}")
async def find_file_generic_experiment_number(experiment_number: int, filename: str) -> str:
    """
    Return the relative path to the env var CEPH_DIR that leads to the requested file if one exists.
    :param experiment_number: Experiment number the file belongs to.
    :param filename: Filename to find
    :return: The relative path to the file in the CEPH_DIR env var.
    """
    path = find_file_experiment_number(ceph_dir=CEPH_DIR, experiment_number=experiment_number, filename=filename)
    if path is None:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST)
    return str(request_path_check(path=path, base_dir=CEPH_DIR))


@app.get("/find_file/generic/user_number/{user_number}")
async def find_file_generic_user_number(user_number: int, filename: str) -> str:
    """
    Return the relative path to the env var CEPH_DIR that leads to the requested file if one exists.
    :param user_number: Experiment number the file belongs to.
    :param filename: Filename to find
    :return: The relative path to the file in the CEPH_DIR env var.
    """
    path = find_file_user_number(ceph_dir=CEPH_DIR, user_number=user_number, filename=filename)
    if path is None:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST)
    return str(request_path_check(path, base_dir=CEPH_DIR))


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
