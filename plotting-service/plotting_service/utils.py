import asyncio
import json
import logging
import re
from contextlib import suppress
from http import HTTPStatus
from pathlib import Path

import websockets
from fastapi import HTTPException
from starlette.requests import Request

logger = logging.getLogger(__name__)


def validate_instrument_name(instrument: str) -> None:
    """
    Validate that the instrument name contains only alphanumeric characters and dashes/underscores.
    Raises HTTPException with 403 Forbidden if the instrument name is invalid.

    :param instrument: The instrument name to validate
    :raises HTTPException: If the instrument name contains invalid characters
    """
    if not re.fullmatch(r"[A-Za-z0-9-_]+", instrument):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Invalid instrument name: must contain only alphanumeric characters, dashes, and underscores",
        )


def safe_check_filepath(filepath: Path, base_path: str) -> None:
    """
    Check to ensure the path does contain the base path and that it does not resolve to some other directory
    :param filepath: the filepath to check
    :param base_path: base path to check against
    :return:
    """
    filepath.resolve(strict=True)
    if not filepath.is_relative_to(base_path):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid path being accessed.")


def _safe_find_file_in_dir(dir_path: Path, base_path: str, filename: str) -> Path | None:
    """
    Check that the directory path is safe and then search for filename in that directory and sub directories
    :param dir_path: Path to check is safe and search in side of
    :param base_path: the base directory of the path often just the /ceph dir on runners
    :param filename: filename to find
    :return: Path to the file or None
    """
    # Do a check as we are handling user entered data here
    try:
        safe_check_filepath(filepath=dir_path, base_path=base_path)
    except OSError:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid path being accessed.") from None

    if dir_path.exists():
        found_paths = list(dir_path.rglob(filename))
        if len(found_paths) > 0 and found_paths[0].exists():
            return found_paths[0]

    return None


def find_file_instrument(ceph_dir: str, instrument: str, experiment_number: int, filename: str) -> Path | None:
    """
    Find a file likely made by automated reduction of an experiment number
    :param ceph_dir: base path of the filename path
    :param instrument: name of the instrument to find the file in
    :param experiment_number: experiment number of the file
    :param filename: name of the file to find
    :return: path to the filename or None
    """
    # Run normal check
    basic_path = Path(ceph_dir) / f"{instrument.upper()}/RBNumber/RB{experiment_number}/autoreduced/{filename}"
    # Do a check as we are handling user entered data here
    with suppress(OSError):
        safe_check_filepath(filepath=basic_path, base_path=ceph_dir)
    if basic_path.exists():
        return basic_path

    # Does the autoreduced/RBNumber folder exist? If so use it, else use unknown
    autoreduced_folder = Path(ceph_dir) / f"{instrument.upper()}/RBNumber/RB{experiment_number}/autoreduced"
    with suppress(OSError):
        safe_check_filepath(filepath=autoreduced_folder, base_path=ceph_dir)
    if autoreduced_folder.exists():
        return _safe_find_file_in_dir(dir_path=autoreduced_folder, base_path=ceph_dir, filename=filename)

    autoreduced_folder = Path(ceph_dir) / f"{instrument.upper()}/RBNumber/unknown/autoreduced"
    return _safe_find_file_in_dir(dir_path=autoreduced_folder, base_path=ceph_dir, filename=filename)


def find_file_experiment_number(ceph_dir: str, experiment_number: int, filename: str) -> Path | None:
    """
    Find the file for the given user_number
    :param ceph_dir: base path of the path
    :param experiment_number: experiment_number of the user who made the file and dir path
    :param filename: filename to find
    :return: Full path to the filename or None
    """
    dir_path = Path(ceph_dir) / f"GENERIC/autoreduce/ExperimentNumbers/{experiment_number}/"
    return _safe_find_file_in_dir(dir_path=dir_path, base_path=ceph_dir, filename=filename)


def find_file_user_number(ceph_dir: str, user_number: int, filename: str) -> Path | None:
    """
    Find the file for the given user_number
    :param ceph_dir: base path of the path
    :param user_number: user number of the user who made the file and dir path
    :param filename: filename to find
    :return: Full path to the filename or None
    """
    dir_path = Path(ceph_dir) / f"GENERIC/autoreduce/UserNumbers/{user_number}/"
    return _safe_find_file_in_dir(dir_path=dir_path, base_path=ceph_dir, filename=filename)


def find_experiment_number(request: Request) -> int:
    """
    Find the experiment number from a request
    :param request: Request to be used to get the experiment number
    :return: Experiment number in the request
    """
    if request.url.path.startswith("/text"):
        return int(request.url.path.split("/")[-1])
    if request.url.path.startswith("/find_file"):
        url_parts = request.url.path.split("/")
        try:
            experiment_number_index = url_parts.index("experiment_number")
            return int(url_parts[experiment_number_index + 1])
        except (ValueError, IndexError):
            logger.warning(
                f"The requested path {request.url.path} does not include an experiment number. "
                f"Permissions cannot be checked"
            )
            raise HTTPException(HTTPStatus.BAD_REQUEST, "Request missing experiment number") from None
    match = re.search(r"%2FRB(\d+)%2F", request.url.query)
    if match is not None:
        return int(match.group(1))

    logger.warning(
        f"The requested nexus metadata path {request.url.path} does not include an experiment number. "
        f"Permissions cannot be checked"
    )
    raise HTTPException(HTTPStatus.BAD_REQUEST, "Request missing experiment number")


def request_path_check(path: Path | None, base_dir: str) -> Path:
    """
    Check if the path is not None, and remove the base dir from the path.
    :param path: Path to check
    :param base_dir: Base dir to remove if present
    :return: Path without the base_dir
    """
    if path is None:
        logger.error("Could not find the file requested.")
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST)
    # Remove CEPH_DIR
    if path.is_relative_to(base_dir):
        path = path.relative_to(base_dir)
    return path


async def get_current_rb_async(instrument: str, timeout: float = 5.0) -> str:
    pv = f"IN:{instrument.upper()}:DAE:_RBNUMBER"
    ws_url = "wss://ndaextweb4.nd.rl.ac.uk/pvws/pv"

    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"type": "subscribe", "pvs": [pv]}))

        try:
            return await asyncio.wait_for(
                _wait_for_pv_update(ws, pv),
                timeout=timeout
            )
        except TimeoutError:
            raise TimeoutError(f"Failed to get PV {pv} within {timeout} seconds") from None


async def _wait_for_pv_update(ws, pv: str) -> str:
    """Helper function to wait for the specific PV update."""
    while True:
        msg = await ws.recv()
        data = json.loads(msg)

        if data.get("type") == "update" and data.get("pv") == pv:
            # VString → RB is in `text`

            return data.get("text") or str(data.get("value"))

def get_current_rb_for_instrument(instrument: str) -> str:
    """
    Given an instrument name, return the rb number (experiment number) of the current experiment on the instrument

    :param instrument: Instrument name to get rb number for
    :return: RB number of the current ISIS run
    """
    return asyncio.run(get_current_rb_async(instrument))
