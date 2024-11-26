import re
from http import HTTPStatus
from pathlib import Path

from fastapi import HTTPException
from starlette.requests import Request

from plotting_service.plotting_api import logger


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
