"""Instrument configuration for live data directories."""

from pathlib import Path

# Mapping of instrument names to their live data subdirectory paths
# These are relative to the CEPH_DIR
INSTRUMENT_LIVE_DATA_PATHS: dict[str, str] = {
    "MARI": "MARI/live_data",
}


def get_supported_instruments() -> list[str]:
    """Return list of supported instrument names."""
    return list(INSTRUMENT_LIVE_DATA_PATHS.keys())


def get_live_data_dir(instrument: str, ceph_dir: str) -> Path | None:
    """Get the live data directory path for an instrument.

    Args:
        instrument: The instrument name (case-insensitive)
        ceph_dir: The base CEPH directory path

    Returns:
        The full path to the live data directory, or None if instrument not supported
    """
    instrument_upper = instrument.upper()
    if instrument_upper not in INSTRUMENT_LIVE_DATA_PATHS:
        return None

    relative_path = INSTRUMENT_LIVE_DATA_PATHS[instrument_upper]
    return Path(ceph_dir) / relative_path
