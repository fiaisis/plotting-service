import re
from http import HTTPStatus
from pathlib import Path

from fastapi import HTTPException
from starlette.requests import Request


def find_file(ceph_dir: str, instrument: str, experiment_number: int, filename: str) -> Path | None:
    # Run normal check
    basic_path = Path(ceph_dir) / f"{instrument.upper()}/RBNumber/RB{experiment_number}/autoreduced/{filename}"

    # Do a check as we are handling user entered data here
    try:
        basic_path.resolve(strict=True)
        if not basic_path.is_relative_to(ceph_dir):
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid path being accessed.")
    except OSError:
        # The OSError can be raised semi-regularly by basic_path.resolve when it can't find it.
        pass

    if basic_path.exists():
        return basic_path

    # Attempt to find file in autoreduced folder
    autoreduced_folder = Path(ceph_dir) / f"{instrument.upper()}/RBNumber/RB{experiment_number}/autoreduced"

    # Do a check as we are handling user entered data here
    try:
        autoreduced_folder.resolve(strict=True)
        if not autoreduced_folder.is_relative_to(ceph_dir):
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid path being accessed")
    except OSError:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid path being accessed.") from None

    if autoreduced_folder.exists():
        found_paths = list(autoreduced_folder.rglob(filename))
        if len(found_paths) > 0 and found_paths[0].exists():
            return found_paths[0]

    return None


def find_experiment_number(request: Request) -> int:
    if request.url.path.startswith("/text"):
        return int(request.url.path.split("/")[-1])
    if request.url.path.startswith("/find_file"):
        url_parts = request.url.path.split("/")
        try:
            experiment_number_index = url_parts.index("experiment_number")
            return int(url_parts[experiment_number_index + 1])
        except (ValueError, IndexError):
            from plotting_service.plotting_api import logger

            logger.warning(
                f"The requested path {request.url.path} does not include an experiment number. "
                f"Permissions cannot be checked"
            )
            raise HTTPException(400, "Request missing experiment number") from None
    else:
        match = re.search(r"%2FRB(\d+)%2F", request.url.query)
        if match is not None:
            return int(match.group(1))
        # Avoiding circular import
        from plotting_service.plotting_api import logger

        logger.warning(
            f"The requested nexus metadata path {request.url.path} does not include an experiment number. "
            f"Permissions cannot be checked"
        )
        raise HTTPException(400, "Request missing experiment number")
