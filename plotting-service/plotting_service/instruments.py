"""Instrument configuration for live data directories."""

from pathlib import Path


def get_live_data_dir(instrument: str, ceph_dir: str) -> Path | None:
    """Get the live data directory path for an instrument.

    Uses convention: {CEPH_DIR}/{INSTRUMENT}/live_data/

    Args:
        instrument: The instrument name (case-insensitive)
        ceph_dir: The base CEPH directory path

    Returns:
        The full path to the live data directory, or None if directory doesn't exist
    """
    instrument_upper = instrument.upper()
    live_data_path = Path(ceph_dir) / instrument_upper / "live_data"

    # Return path only if directory exists
    if live_data_path.exists() and live_data_path.is_dir():
        return live_data_path

    return None
