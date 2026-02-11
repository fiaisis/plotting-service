"""Live data monitoring service for file watching and SSE event generation."""

import asyncio
import contextlib
import logging
import os
import typing
from pathlib import Path

logger = logging.getLogger(__name__)

PRODUCTION = os.environ.get("PRODUCTION", "False").lower() == "true"


def get_file_snapshot(directory: Path) -> dict[str, float]:
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


async def generate_file_change_events(
    live_data_path: Path,
    base_path: str,
    instrument: str,
    keepalive_interval: int = 30,
    poll_interval: int = 5,
) -> typing.AsyncGenerator[str, None]:
    """Generate SSE events for file changes using polling.

    :param live_data_path: Path to the live data directory to watch
    :param base_path: Base path for calculating relative directory
    :param instrument: Instrument name for logging
    :param keepalive_interval: Seconds between keepalive messages
    :param poll_interval: Seconds between directory polls
    :yield: SSE formatted event strings
    """
    # Send initial connected event
    relative_dir = str(live_data_path.relative_to(base_path))
    yield f'event: connected\ndata: {{"directory": "{relative_dir}"}}\n\n'

    # Build initial snapshot of files and their modification times
    file_snapshot = get_file_snapshot(live_data_path)
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
            current_snapshot = get_file_snapshot(live_data_path)

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


def get_live_data_directory(instrument: str, ceph_dir: str) -> Path | None:
    """Return the path to the instrument's live data directory.

    :param instrument: The instrument name
    :param ceph_dir: Base CEPH directory path
    :return: Path to live data directory, or None if it doesn't exist
    """
    instrument_upper = instrument.upper()
    generic_dir = "GENERIC" if PRODUCTION else "GENERIC-staging"
    live_data_path = Path(ceph_dir) / generic_dir / "livereduce" / instrument_upper

    if not (live_data_path.exists() and live_data_path.is_dir()):
        return None

    return live_data_path
