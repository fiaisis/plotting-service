"""Image processing service for IMAT and related image operations."""

from pathlib import Path

from PIL import Image

IMAGE_SUFFIXES = {".tif", ".tiff"}


def find_latest_image_in_directory(directory: Path) -> Path | None:
    """Return the newest image file under directory, searching recursively.

    :param directory: The directory to search for images
    :return: Path to the newest image file, or None if no images found
    """
    latest_path: Path | None = None
    latest_mtime: float = 0.0

    for entry in directory.rglob("*"):
        if entry.is_file() and entry.suffix.lower() in IMAGE_SUFFIXES:
            mtime = entry.stat().st_mtime
            if mtime > latest_mtime:
                latest_path = entry
                latest_mtime = mtime

    return latest_path


def convert_image_to_rgb_array(image_path: Path) -> tuple[list[int], int, int]:
    """Convert image into a list of byte values to be used by frontend H5Web
    interface.

    :param image_path: Path to the image file
    :return: Tuple of (list of byte values, width, height)
    """
    with Image.open(image_path) as image:
        converted = image.convert("RGB")
        width, height = converted.size
        data = list(converted.tobytes())

    return data, width, height
