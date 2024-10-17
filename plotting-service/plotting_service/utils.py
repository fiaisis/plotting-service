import re
from pathlib import Path

from fastapi import HTTPException
from starlette.requests import Request

from plotting_service.plotting_api import logger


def find_file(ceph_dir: str, instrument: str, experiment_number: int, filename: str) -> Path | None:
    # Run normal check
    basic_path = Path(ceph_dir) / f"{instrument.upper()}/RBNumber/RB{experiment_number}/autoreduced/{filename}"
    if basic_path.exists():
        return basic_path

    # Attempt to find file in autoreduced folder
    autoreduced_folder = Path(ceph_dir) / f"{instrument.upper()}/RBNumber/RB{experiment_number}/autoreduced"
    if autoreduced_folder.exists():
        found_paths = list(autoreduced_folder.rglob(filename))
        if len(found_paths) > 0 and found_paths[0].exists():
            return found_paths[0]

    return None


def find_experiment_number(request: Request) -> int:
    experiment_number = None
    if request.url.path.startswith("/text"):
        experiment_number = int(request.url.path.split("/")[-1])
    elif request.url.path.startswith("/find_file"):
        url_parts = request.url.path.split("/")
        last_part_seen = url_parts[-1]
        for part in reversed(url_parts):
            if "experiment_number" in part:
                experiment_number = int(last_part_seen)
            else:
                last_part_seen = part
        if experiment_number is None:
            logger.warning(
                f"The requested path {request.url.path} does not include an experiment number. "
                f"Permissions cannot be checked"
            )
            raise HTTPException(400, "Request missing experiment number")
    else:
        match = re.search(r"%2FRB(\d+)%2F", request.url.query)
        if match is not None:
            experiment_number = int(match.group(1))
        else:
            logger.warning(
                f"The requested nexus metadata path {request.url.path} does not include an experiment number. "
                f"Permissions cannot be checked"
            )
            raise HTTPException(400, "Request missing experiment number")
    return experiment_number
