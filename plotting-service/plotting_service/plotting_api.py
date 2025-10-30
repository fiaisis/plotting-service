"""
Main module
"""

import importlib
import json
import logging
import mimetypes
import os
import re
import sys
import typing
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse

from plotting_service.auth import get_experiments_for_user, get_user_from_token
from plotting_service.exceptions import AuthError
from plotting_service.model import Metadata
from plotting_service.utils import (
    find_experiment_number,
    find_file_experiment_number,
    find_file_instrument,
    find_file_user_number,
    request_path_check,
)

h5_fastapi_utils = typing.cast("typing.Any", importlib.import_module("h5grove.fastapi_utils"))
router = h5_fastapi_utils.router
settings = h5_fastapi_utils.settings

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
IMAT_DIR: Path = Path(os.getenv("IMAT_DIR", "/imat")).resolve()
logger.info("Setting IMAT directory to %s", IMAT_DIR)
IMAGE_SUFFIXES = {".tif", ".tiff"}
settings.base_dir = Path(CEPH_DIR).resolve()
DEV_MODE = os.environ.get("DEV_MODE", "False").lower() == "true"
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
        with Path(f"{CEPH_DIR}/GENERIC/autoreduce/healthy_file.txt").open("r") as fle:
            lines = fle.readlines()
            if lines[0] != "This is a healthy file! You have read it correctly!\n":
                raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE)
        return "ok"
    except:  # noqa: E722
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


@app.get("/processed_data/{instrument}/{experiment_number}")
async def get_processed_data(instrument: str, experiment_number: int, filename: str) -> JSONResponse:
    filename = (
        CEPH_DIR
        + "/"
        + str(
            request_path_check(
                path=find_file_instrument(
                    ceph_dir=CEPH_DIR, instrument=instrument, experiment_number=experiment_number, filename=filename
                ),
                base_dir=CEPH_DIR,
            )
        )
    )

    try:
        await ensure_path_exists(filename, "/")

        try:
            await ensure_path_exists(filename, "/ws_out")
            await ensure_path_exists(filename, "/ws_out/data")
            axis_x = await h5_fastapi_utils.get_data(file=filename, path="/ws_out/data/energy")
            axis_y = await h5_fastapi_utils.get_data(file=filename, path="/ws_out/data/polar")
            data = await h5_fastapi_utils.get_data(file=filename, path="/ws_out/data/data")

        except HTTPException:
            await ensure_path_exists(filename, "/mantid_workspace_1")
            await ensure_path_exists(filename, "/mantid_workspace_1/workspace")
            axis_x = await h5_fastapi_utils.get_data(file=filename, path="/mantid_workspace_1/workspace/axis1")
            axis_y = await h5_fastapi_utils.get_data(file=filename, path="/mantid_workspace_1/workspace/axis2")
            data = await h5_fastapi_utils.get_data(file=filename, path="/mantid_workspace_1/workspace/values")

        data_data = typing.cast("list[list[float]]", json.loads(data.body.decode()))
        axis_x_data = typing.cast("list[float]", json.loads(axis_x.body.decode()))
        axis_y_data = typing.cast("list[float]", json.loads(axis_y.body.decode()))

        formatted_list = [
            [axis_x_data[x], axis_y_data[y], value] for y, row in enumerate(data_data) for x, value in enumerate(row)
        ]
        return JSONResponse(formatted_list)

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Unknown error") from None


@app.get("/echarts_meta/{instrument}/{experiment_number}")
async def get_echarts_metadata(instrument: str, experiment_number: int, filename: str, path: str):
    filename = (
        CEPH_DIR
        + "/"
        + str(
            request_path_check(
                path=find_file_instrument(
                    ceph_dir=CEPH_DIR, instrument=instrument, experiment_number=experiment_number, filename=filename
                ),
                base_dir=CEPH_DIR,
            )
        )
    )

    try:
        await ensure_path_exists(filename, "/")
        try:
            await ensure_path_exists(filename, "/ws_out")
            axes_names = await h5_fastapi_utils.get_attr(file=filename, path="ws_out/data/data", attr_keys=["axes"])
            shape = await h5_fastapi_utils.get_meta(file=filename, path="ws_out/data/data")
            max_axis_x = await h5_fastapi_utils.get_stats(file=filename, path="ws_out/data/energy")
            min_axis_x = await h5_fastapi_utils.get_stats(file=filename, path="ws_out/data/energy")
            max_axis_y = await h5_fastapi_utils.get_stats(file=filename, path="ws_out/data/polar")
            min_axis_y = await h5_fastapi_utils.get_stats(file=filename, path="ws_out/data/polar")
            return Metadata(
                filename=filename,
                shape=len(json.loads(shape.body)["shape"]),
                axes_labels=json.loads(axes_names.body),
                x_axis_min=json.loads(min_axis_x.body)["min"],
                x_axis_max=json.loads(max_axis_x.body)["max"],
                y_axis_min=json.loads(min_axis_y.body)["min"],
                y_axis_max=json.loads(max_axis_y.body)["max"],
            )
        except HTTPException:
            await ensure_path_exists(filename, "/mantid_workspace_1")
            await ensure_path_exists(filename, "/mantid_workspace_1/workspace")
            values_meta = await h5_fastapi_utils.get_meta(file=filename, path="/mantid_workspace_1/workspace/values")
            atr_axis1 = await h5_fastapi_utils.get_attr(
                file=filename, path="/mantid_workspace_1/workspace/axis1", attr_keys=["units"]
            )
            atr_axis2 = await h5_fastapi_utils.get_attr(
                file=filename, path="/mantid_workspace_1/workspace/axis2", attr_keys=["units"]
            )
            stat_axis1 = await h5_fastapi_utils.get_stats(file=filename, path="/mantid_workspace_1/workspace/axis1")
            stat_axis2 = await h5_fastapi_utils.get_stats(file=filename, path="/mantid_workspace_1/workspace/axis2")

            atr_axis1_data = json.loads(atr_axis1.body.decode())
            atr_axis2_data = json.loads(atr_axis2.body.decode())
            stat_axis1_data = json.loads(stat_axis1.body.decode())
            stat_axis2_data = json.loads(stat_axis2.body.decode())

            return Metadata(
                filename=filename,
                shape=len(json.loads(values_meta.body)["shape"]),
                axes_labels=[atr_axis1_data["units"], atr_axis2_data["units"]],
                x_axis_min=stat_axis1_data["min"],
                x_axis_max=stat_axis1_data["max"],
                y_axis_min=stat_axis2_data["min"],
                y_axis_max=stat_axis2_data["max"],
            )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Unknown error") from None


@app.get("/echarts_data/{instrument}/{experiment_number}")
async def get_echarts_data(instrument: str, experiment_number: int, filename: str, selection: int) -> JSONResponse:
    filename = (
        CEPH_DIR
        + "/"
        + str(
            request_path_check(
                path=find_file_instrument(
                    ceph_dir=CEPH_DIR, instrument=instrument, experiment_number=experiment_number, filename=filename
                ),
                base_dir=CEPH_DIR,
            )
        )
    )

    try:
        await ensure_path_exists(filename, "/")

        try:
            await ensure_path_exists(filename, "/ws_out")
            await ensure_path_exists(filename, "/ws_out/data")
            axis = await h5_fastapi_utils.get_data(file=filename, path="/ws_out/data/energy")
            data = await h5_fastapi_utils.get_data(file=filename, path="/ws_out/data/data", selection=selection)
        except HTTPException:
            await ensure_path_exists(filename, "/mantid_workspace_1")
            await ensure_path_exists(filename, "/mantid_workspace_1/workspace")
            axis = await h5_fastapi_utils.get_data(file=filename, path="/mantid_workspace_1/workspace/axis1")
            data = await h5_fastapi_utils.get_data(
                file=filename, path="/mantid_workspace_1/workspace/values", selection=selection
            )

        data_data = typing.cast("list[float]", json.loads(data.body.decode()))
        axis_data = typing.cast("list[float]", json.loads(axis.body.decode()))
        return JSONResponse(bucket_and_join_data(axis_data, data_data))

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Unknown error") from None


# Helper to raise 404 if a meta request fails
async def ensure_path_exists(file: str, path: str) -> None:
    try:
        await h5_fastapi_utils.get_meta(file=file, path=path)
    except h5_fastapi_utils.H5GroveException:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=f"Path not found: {path}") from None


def bucket_and_join_data(axis: list[float], data: list[float]) -> list[list[float]]:
    axis_bucketed = [(axis[i] + axis[i + 1]) / 2 for i in range(len(axis) - 1)]
    return [[x, y] for x, y in zip(axis_bucketed, data, strict=False)]


@app.middleware("http")
async def check_permissions(request: Request, call_next: typing.Callable[..., typing.Any]) -> typing.Any:  # noqa: C901, PLR0911
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


def _latest_image_in_dir(directory: Path) -> Path | None:
    """Return the newest image file under directory, searching recursively."""
    latest_path: Path | None = None
    latest_mtime: float = 0.0
    for entry in directory.rglob("*"):
        if entry.is_file() and entry.suffix.lower() in IMAGE_SUFFIXES:
            mtime = entry.stat().st_mtime
            if mtime > latest_mtime:
                latest_path = entry
                latest_mtime = mtime
    return latest_path


@app.get(
    "/imat/latest-image",
    summary="Fetch the latest IMAT image",
)
async def get_latest_imat_image() -> FileResponse:
    """Return the newest image from any RB folder within the IMAT directory."""
    # Find RB* directories directly under IMAT root; ignore unrelated folders
    rb_dirs = [d for d in IMAT_DIR.iterdir() if d.is_dir() and re.fullmatch(r"RB\d+", d.name)]
    if not rb_dirs:
        raise HTTPException(HTTPStatus.NOT_FOUND, "No RB folders under IMAT_DIR")

    latest_path: Path | None = None
    latest_mtime: float = 0.0

    for rb_dir in rb_dirs:
        rb_latest = _latest_image_in_dir(rb_dir)
        if rb_latest is None:
            continue
        rb_mtime = rb_latest.stat().st_mtime
        # Keep track of the most recent image seen so far across all RB folders
        if rb_mtime > latest_mtime:
            latest_path = rb_latest
            latest_mtime = rb_mtime

    if latest_path is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "No images found in IMAT_DIR")

    # Derive an appropriate media type so clients can handle the image correctly
    media_type, _ = mimetypes.guess_type(str(latest_path))
    if media_type is None:
        media_type = "application/octet-stream"

    return FileResponse(
        latest_path,
        media_type=media_type,
        filename=latest_path.name,
    )


app.include_router(router)
