import asyncio
import contextlib
import logging
import os
import sys
import typing
from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from plotting_service.utils import safe_check_filepath

LiveDataRouter = APIRouter(prefix="/live")

CEPH_DIR = os.environ.get("CEPH_DIR", "/ceph")

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
    live_data_path = _get_live_data_directory(instrument)

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


def _get_live_data_directory(instrument: str) -> Path:
    """Return the path to the instrument's live data directory."""
    instrument_upper = instrument.upper()
    live_data_path = Path(CEPH_DIR) / "GENERIC" / "livereduce" / instrument_upper

    safe_check_filepath(live_data_path, CEPH_DIR + "/GENERIC/livereduce")

    if not (live_data_path.exists() and live_data_path.is_dir()):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Live data directory for '{instrument}' not found"
        )

    return live_data_path


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

    live_data_path = _get_live_data_directory(instrument)

    return StreamingResponse(
        _event_generator(live_data_path, instrument, keepalive_interval, poll_interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _event_generator(
    live_data_path: Path, instrument: str, keepalive_interval: int = 30, poll_interval: int = 5
) -> typing.AsyncGenerator[str, None]:
    """Generate SSE events for file changes using polling."""
    # Send initial connected event
    relative_dir = str(live_data_path.relative_to(CEPH_DIR))
    yield f'event: connected\ndata: {{"directory": "{relative_dir}"}}\n\n'

    # Build initial snapshot of files and their modification times
    file_snapshot = _get_file_snapshot(live_data_path)
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
                yield ": keepalive\n\n"
                polls_since_keepalive = 0

            # Get current state
            current_snapshot = _get_file_snapshot(live_data_path)

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
                    logger.info(
                        f"File modified: {filename} (mtime {file_snapshot[filename]} -> {current_snapshot[filename]})"
                    )
                    yield f'event: file_changed\ndata: {{"file": "{filename}", "change_type": "modified"}}\n\n'

            # Update snapshot for next iteration
            file_snapshot = current_snapshot

    except asyncio.CancelledError:
        logger.info(f"SSE connection closed for instrument {instrument}")
    except Exception as e:
        logger.exception(f"Error in SSE event generator for {instrument}")
        yield f'event: error\ndata: {{"error": "{e!s}"}}\n\n'
