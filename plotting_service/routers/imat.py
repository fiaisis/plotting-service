import logging
import os
import re
import sys
import typing
from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from PIL import Image
from starlette.responses import JSONResponse, Response

from plotting_service.services.image_service import (
    IMAGE_SUFFIXES,
    convert_image_to_rgb_array,
    find_latest_image_in_directory,
)
from plotting_service.utils import safe_check_filepath

ImatRouter = APIRouter()

IMAT_DIR: Path = Path(os.getenv("IMAT_DIR", "/imat")).resolve()
CEPH_DIR = os.environ.get("CEPH_DIR", "/ceph")

stdout_handler = logging.StreamHandler(stream=sys.stdout)
logging.basicConfig(
    handlers=[stdout_handler],
    format="[%(asctime)s]-%(name)s-%(levelname)s: %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


@ImatRouter.get("/imat/latest-image", summary="Fetch the latest IMAT image")
async def get_latest_imat_image(
    downsample_factor: typing.Annotated[
        int,
        Query(
            ge=1,
            le=64,
            description="Integer factor to reduce each dimension by (1 keeps original resolution).",
        ),
    ] = 8,
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
        rb_latest = find_latest_image_in_directory(rb_dir)
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
        data, original_width, original_height, sampled_width, sampled_height = convert_image_to_rgb_array(
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


@ImatRouter.get("/imat/list-images", summary="List images in a directory")
async def list_imat_images(
    path: typing.Annotated[
        str, Query(..., description="Path to the directory containing images, relative to CEPH_DIR")
    ],
) -> list[str]:
    """Return a sorted list of TIFF images in the given directory."""

    dir_path = (Path(CEPH_DIR) / path).resolve()
    # Security: Ensure path is within CEPH_DIR
    try:
        safe_check_filepath(dir_path, CEPH_DIR)
    except FileNotFoundError as err:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Directory not found") from err

    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Directory not found")

    images = [entry.name for entry in dir_path.iterdir() if entry.is_file() and entry.suffix.lower() in IMAGE_SUFFIXES]

    return sorted(images)


@ImatRouter.get("/imat/image", summary="Fetch a specific TIFF image as raw data")
async def get_imat_image(
    path: typing.Annotated[str, Query(..., description="Path to the TIFF image file, relative to CEPH_DIR")],
        downsample_factor: typing.Annotated[
            int,
            Query(
                ge=1,
                le=64,
                description="Integer factor to reduce each dimension by (1 keeps original resolution).",
            ),
        ] = 1,
) -> Response:
    """Return the raw data of a specific TIFF image as binary."""

    image_path = (Path(CEPH_DIR) / path).resolve()
    # Security: Ensure path is within CEPH_DIR
    try:
        safe_check_filepath(image_path, CEPH_DIR)
    except FileNotFoundError as err:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Directory not found") from err

    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Image not found")

    try:
        with Image.open(image_path) as img:
            original_width, original_height = img.size

            if downsample_factor > 1:
                target_width = max(1, round(original_width / downsample_factor))
                target_height = max(1, round(original_height / downsample_factor))
                display_img = img.resize((target_width, target_height), Image.Resampling.NEAREST)
            else:
                display_img = img

            sampled_width, sampled_height = display_img.size
            # For 16-bit TIFFs, tobytes() returns raw 16-bit bytes
            data_bytes = display_img.tobytes()

        headers = {
            "X-Image-Width": str(sampled_width),
            "X-Image-Height": str(sampled_height),
            "X-Original-Width": str(original_width),
            "X-Original-Height": str(original_height),
            "X-Downsample-Factor": str(downsample_factor),
            "Access-Control-Expose-Headers": (
                "X-Image-Width, X-Image-Height, X-Original-Width, X-Original-Height, X-Downsample-Factor"
            ),
        }

        return Response(
            content=data_bytes,
            media_type="application/octet-stream",
            headers=headers
        )

    except Exception as exc:
        logger.error(f"Failed to process image {image_path}: {exc}")
        raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to process image") from exc
