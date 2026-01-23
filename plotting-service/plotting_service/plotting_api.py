"""Main module."""

import asyncio
import contextlib
import importlib
import logging
import os
import re
import sys
import typing
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from h5grove.fastapi_utils import router, settings
from PIL import Image
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, StreamingResponse

from plotting_service.auth import get_experiments_for_user, get_user_from_token
from plotting_service.exceptions import AuthError
from plotting_service.utils import (
    find_experiment_number,
    find_file_experiment_number,
    find_file_instrument,
    find_file_user_number,
    get_current_rb_async,
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

IMAT_DIR: Path = Path(os.getenv("IMAT_DIR", "/imat")).resolve()
logger.info("Setting IMAT directory to %s", IMAT_DIR)
IMAGE_SUFFIXES = {".tif", ".tiff"}

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
    """Health check endpoint :return: "ok"."""
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
    """Return the relative path to the env var CEPH_DIR that leads to the
    requested file if one exists.

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
    """Return the relative path to the env var CEPH_DIR that leads to the
    requested file if one exists.

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
    """Return the relative path to the env var CEPH_DIR that leads to the
    requested file if one exists.

    :param user_number: Experiment number the file belongs to.
    :param filename: Filename to find
    :return: The relative path to the file in the CEPH_DIR env var.
    """
    path = find_file_user_number(ceph_dir=CEPH_DIR, user_number=user_number, filename=filename)
    if path is None:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST)
    return str(request_path_check(path, base_dir=CEPH_DIR))


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
    if request.url.path in ("/healthz", "/docs"):
        return await call_next(request)
    if request.url.path.startswith("/live"):
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


def _convert_image_to_rgb_array(image_path: Path, downsample_factor: int) -> tuple[list[int], int, int, int, int]:
    """Convert image into a RGB byte array to be used by frontend H5Web
    interface."""
    with Image.open(image_path) as image:
        original_width, original_height = image.size
        converted = image.convert("RGB")

        if downsample_factor > 1:
            # Reduce resolution while keeping at least 1x1 output
            target_width = max(1, round(original_width / downsample_factor))
            target_height = max(1, round(original_height / downsample_factor))
            converted = converted.resize(
                (target_width, target_height), Image.Resampling.LANCZOS
            )  # Lanczos gives higher-quality downsampling

        sampled_width, sampled_height = converted.size
        data = list(converted.tobytes())

    return data, original_width, original_height, sampled_width, sampled_height


@app.get("/imat/latest-image", summary="Fetch the latest IMAT image")
async def get_latest_imat_image(
    downsample_factor: int = Query(
        default=8, ge=1, le=64, description="Integer factor to reduce each dimension by (1 keeps original resolution)."
    ),
) -> JSONResponse:
    """Return the latest image from any RB folder within the IMAT directory."""
    # Find RB* folders under the IMAT root
    rb_dirs = [d for d in IMAT_DIR.iterdir() if d.is_dir() and re.fullmatch(r"RB\d+", d.name)]

    if not rb_dirs:
        raise HTTPException(HTTPStatus.NOT_FOUND, "No RB folders under IMAT_DIR")

    latest_path: Path | None = None
    latest_mtime: float = 0.0

    # Find latest image across all RB folders
    for rb_dir in rb_dirs:
        rb_latest = _latest_image_in_dir(rb_dir)
        if rb_latest is None:
            continue

        rb_mtime = rb_latest.stat().st_mtime

        # Track the single most recent image across all RB folders
        if rb_mtime > latest_mtime:
            latest_path = rb_latest
            latest_mtime = rb_mtime

    if latest_path is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "No images found in IMAT_DIR")

    # Convert the image to RGB array
    try:
        data, original_width, original_height, sampled_width, sampled_height = _convert_image_to_rgb_array(
            latest_path, downsample_factor
        )
    except Exception as exc:
        logger.error("Failed to convert IMAT image at %s", latest_path, exc_info=exc)
        raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to convert IMAT image") from exc

    # Calculate effective downsample factor
    effective_downsample = original_width / sampled_width if sampled_width else 1

    payload = {
        "data": data,
        "shape": [sampled_height, sampled_width, 3],
        "originalWidth": original_width,
        "originalHeight": original_height,
        "sampledWidth": sampled_width,
        "sampledHeight": sampled_height,
        "downsampleFactor": effective_downsample,
    }
    return JSONResponse(payload)



# --- Live App Definition ---
live_app = FastAPI()

# @live_app.middleware("http")
# async def check_live_permissions(request: Request, call_next: typing.Callable[..., typing.Any]) -> typing.Any:
#     """
#     Middleware for the live app that checks if the user has permission
#     to view the *current* experiment on the requested instrument.
#     """
#     if DEV_MODE:
#         return await call_next(request)
#     if request.method == "OPTIONS":
#         return await call_next(request)
#     if request.url.path in ("/healthz", "/docs", "/openapi.json"):
#         return await call_next(request)
#
#     logger.info(f"Checking live permissions for {request.url.path}")
#
#     auth_header = request.headers.get("Authorization")
#     if auth_header is None:
#         raise HTTPException(HTTPStatus.UNAUTHORIZED, "Unauthenticated")
#
#     token = auth_header.split(" ")[1]
#
#     # API Key check (if applicable globally, otherwise remove/adapt)
#     api_key = os.environ.get("API_KEY", "")
#     if token == api_key and api_key != "":
#         return await call_next(request)
#
#     try:
#         user = get_user_from_token(token)
#     except AuthError:
#         raise HTTPException(HTTPStatus.FORBIDDEN, detail="Forbidden") from None
#
#     if user.role == "staff":
#         return await call_next(request)
#
#
#     file_param = request.query_params.get("file")
#     if not file_param:
#
#         logger.warning(f"Request to live app without 'file' param: {request.url}")
#
#         if request.url.path == "/": # Root of sub-app
#              return await call_next(request)
#         raise HTTPException(HTTPStatus.BAD_REQUEST, "Missing 'file' parameter for live check")
#
#     # Assuming structure: INSTRUMENT/RBnumber/...
#     parts = Path(file_param).parts
#     if not parts or parts[0] == "/" or parts[0] == ".":
#          raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid file path format")
#
#     instrument = parts[0]
#
#     try:
#         current_rb = await get_current_rb_async(instrument)
#     except Exception as e:
#         logger.error(f"Failed to get current RB for instrument {instrument}: {e}")
#         # If we can't check 'live' status, fail safe
#         raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to verify live experiment status")
#
#
#     try:
#         # It usually comes as just the number from the PV, but handle "RB" prefix just in case
#         if current_rb.upper().startswith("RB"):
#             current_rb_int = int(current_rb[2:])
#         else:
#             current_rb_int = int(current_rb)
#     except ValueError:
#          logger.error(f"Invalid RB number format from PV: {current_rb}")
#          raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "Invalid live experiment data")
#
#     logger.info(f"Checking if user {user.user_number} has access to current RB {current_rb_int} on {instrument}")
#     allowed_experiments = get_experiments_for_user(user)
#
#     if current_rb_int in allowed_experiments:
#         return await call_next(request)
#
#     logger.warning(f"User {user.user_number} denied access to live experiment {current_rb_int}")
#     raise HTTPException(HTTPStatus.FORBIDDEN, detail="Forbidden: You do not have access to the current live experiment")

live_app.include_router(router)

@live_app.get("/live-data/{instrument}/files", summary="List files in instrument's live data directory")
async def get_live_data_files(instrument: str) -> list[str]:
    """Return list of files in the instrument's live data directory.

    :param instrument: The instrument name
    :return: List of filenames in the live data directory
    """

    # Validate instrument to prevent path traversal or invalid characters
    if (
        ".." in instrument
        or "/" in instrument
        or "\\" in instrument
        or "~" in instrument
    ):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN)

    instrument_upper = instrument.upper()
    live_data_path = Path(CEPH_DIR) / "GENERIC" / "livereduce" / instrument_upper

    if not (live_data_path.exists() and live_data_path.is_dir()):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND,
                            detail=f"Live data directory for '{instrument}' not found")

    files = [f.name for f in live_data_path.iterdir() if f.is_file()]
    return sorted(files)

def _get_file_snapshot(directory: Path) -> dict[str, float]:
    """Get a snapshot of all files in a directory with their modification times.

    :param directory: The directory to scan
    :return: Dictionary mapping filename to modification time
    """
    snapshot: dict[str, float] = {}
    try:
        for entry in directory.iterdir():
            if entry.is_file():
                # File may have been deleted between iterdir and stat

                contextlib.suppress(OSError)
                snapshot[entry.name] = entry.stat().st_mtime
    except OSError as e:
        logger.warning(f"Error scanning directory {directory}: {e}")
    return snapshot


@live_app.get("/live-data/{instrument}", summary="SSE endpoint for live data file changes")
async def live_data(instrument: str, poll_interval: int = 2, keepalive_interval: int = 30) -> StreamingResponse:
    """SSE endpoint that watches the instrument's live data directory and sends events when files change.

    Uses polling-based approach for reliable detection on network file systems.

    :param instrument: The instrument name
    :param poll_interval: The interval in seconds between directory polls (default: 2 seconds)
    :param keepalive_interval: The interval in seconds between keepalive messages (default: 30 seconds)
    :return: StreamingResponse with SSE events
    """
    if poll_interval < 1:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Poll interval must be at least 1 second")
    if keepalive_interval < 5:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Keepalive interval must be at least 5 seconds")

    # Validate instrument to prevent path traversal or invalid characters
    if (
        ".." in instrument
        or "/" in instrument
        or "\\" in instrument
        or "~" in instrument
    ):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN)

    instrument_upper = instrument.upper()
    live_data_dir = Path(CEPH_DIR) / "GENERIC" / "livereduce" / instrument_upper

    if not (live_data_dir.exists() and live_data_dir.is_dir()):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND,
                            detail=f"Live data directory for '{instrument}' not found")

    if live_data_dir is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND,
                            detail=f"Live data directory for '{instrument}' not found")

    async def event_generator() -> typing.AsyncGenerator[str, None]:
        """Generate SSE events for file changes using polling."""
        # Send initial connected event
        relative_dir = str(live_data_dir.relative_to(CEPH_DIR))
        yield f'event: connected\ndata: {{"directory": "{relative_dir}"}}\n\n'

        # Build initial snapshot of files and their modification times
        file_snapshot = _get_file_snapshot(live_data_dir)
        logger.info(f"Initial snapshot for {instrument}: {len(file_snapshot)} files")

        # Track time since last keepalive
        polls_since_keepalive = 0
        polls_per_keepalive = keepalive_interval // poll_interval

        try:
            while True:
                await asyncio.sleep(poll_interval)
                polls_since_keepalive += 1

                # Send keepalive to prevent proxy/browser timeouts
                if polls_since_keepalive >= polls_per_keepalive:
                    yield ': keepalive\n\n'
                    polls_since_keepalive = 0

                # Get current state
                current_snapshot = _get_file_snapshot(live_data_dir)

                # Check for changes
                previous_files = set(file_snapshot.keys())
                current_files = set(current_snapshot.keys())

                # Detect added files
                for filename in current_files - previous_files:
                    logger.info(f"File added: {filename}")
                    yield f'event: file_changed\ndata: {{"file": "{filename}", "change_type": "added"}}\n\n'

                # Detect deleted files
                for filename in previous_files - current_files:
                    logger.info(f"File deleted: {filename}")
                    yield f'event: file_changed\ndata: {{"file": "{filename}", "change_type": "deleted"}}\n\n'

                # Detect modified files (same name, different mtime)
                for filename in current_files & previous_files:
                    if current_snapshot[filename] != file_snapshot[filename]:
                        logger.info(f"File modified: {filename} "
                                    f"(mtime {file_snapshot[filename]} -> {current_snapshot[filename]})")
                        yield f'event: file_changed\ndata: {{"file": "{filename}", "change_type": "modified"}}\n\n'

                # Update snapshot for next iteration
                file_snapshot = current_snapshot

        except asyncio.CancelledError:
            logger.info(f"SSE connection closed for instrument {instrument}")
        except Exception as e:
            logger.exception(f"Error in SSE event generator for {instrument}")
            yield f'event: error\ndata: {{"error": "{e!s}"}}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

# Mount the live app
app.mount("/live", live_app)
app.include_router(router)
