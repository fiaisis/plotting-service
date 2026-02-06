import logging
import os
import sys
from http import HTTPStatus

from fastapi import APIRouter, HTTPException
from starlette.responses import PlainTextResponse

from plotting_service.utils import (
    find_file_experiment_number,
    find_file_instrument,
    find_file_user_number,
    request_path_check,
)

CEPH_DIR = os.environ.get("CEPH_DIR", "/ceph")

stdout_handler = logging.StreamHandler(stream=sys.stdout)
logging.basicConfig(
    handlers=[stdout_handler],
    format="[%(asctime)s]-%(name)s-%(levelname)s: %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

PlottingRouter = APIRouter()


@PlottingRouter.get(
    "/text/instrument/{instrument}/experiment_number/{experiment_number}", response_class=PlainTextResponse
)
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


@PlottingRouter.get("/find_file/instrument/{instrument}/experiment_number/{experiment_number}")
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


@PlottingRouter.get("/find_file/generic/experiment_number/{experiment_number}")
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


@PlottingRouter.get("/find_file/generic/user_number/{user_number}")
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
