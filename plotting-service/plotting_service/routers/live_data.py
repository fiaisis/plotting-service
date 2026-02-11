import logging
import os
import sys
from http import HTTPStatus

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from plotting_service.services.live_data_service import (
    generate_file_change_events,
    get_live_data_directory,
)
from plotting_service.utils import safe_check_filepath

LiveDataRouter = APIRouter(prefix="/live")

CEPH_DIR = os.environ.get("CEPH_DIR", "/ceph")
GENERIC_DIR = "GENERIC" if os.environ.get("PRODUCTION", "").lower() == "true" else "GENERIC-staging"

stdout_handler = logging.StreamHandler(stream=sys.stdout)
logging.basicConfig(
    handlers=[stdout_handler],
    format="[%(asctime)s]-%(name)s-%(levelname)s: %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

MINIMUM_KEEP_ALIVE_INTERVAL = 5


@LiveDataRouter.get("/live-data/{instrument}/files", summary="List files in instrument's live data directory")
async def get_live_data_files(instrument: str) -> list[str]:
    """Return list of files in the instrument's live data directory.

    :param instrument: The instrument name
    :return: List of filenames in the live data directory
    """
    live_data_path = get_live_data_directory(instrument, CEPH_DIR)

    if live_data_path is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Live data directory for '{instrument}' not found"
        )

    safe_check_filepath(live_data_path, CEPH_DIR + f"/{GENERIC_DIR}/livereduce")

    files = [f.name for f in live_data_path.iterdir() if f.is_file()]
    return sorted(files)


@LiveDataRouter.get("/live-data/{instrument}", summary="SSE endpoint for live data file changes")
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
    if keepalive_interval < MINIMUM_KEEP_ALIVE_INTERVAL:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Keepalive interval must be at least 5 seconds")

    live_data_path = get_live_data_directory(instrument, CEPH_DIR)

    if live_data_path is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Live data directory for '{instrument}' not found"
        )

    safe_check_filepath(live_data_path, CEPH_DIR + f"/{GENERIC_DIR}/livereduce")

    return StreamingResponse(
        generate_file_change_events(live_data_path, CEPH_DIR, instrument, keepalive_interval, poll_interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
