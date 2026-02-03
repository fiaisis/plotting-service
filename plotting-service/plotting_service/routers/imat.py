import logging
import os
import re
import sys
from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from PIL import Image
from starlette.responses import JSONResponse

ImatRouter = APIRouter()

IMAT_DIR: Path = Path(os.getenv("IMAT_DIR", "/imat")).resolve()

stdout_handler = logging.StreamHandler(stream=sys.stdout)
logging.basicConfig(
    handlers=[stdout_handler],
    format="[%(asctime)s]-%(name)s-%(levelname)s: %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = {".tif", ".tiff"}


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


@ImatRouter.get("/imat/latest-image", summary="Fetch the latest IMAT image")
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
