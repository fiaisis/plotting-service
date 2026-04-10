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


def convert_image_to_rgb_array(image_path: Path, downsample_factor: int) -> tuple[list[int], int, int, int, int]:
    """Convert image into a RGB byte array to be used by frontend H5Web interface.

    :param image_path: Path to the image file
    :param downsample_factor: Factor to reduce resolution (1 keeps original)
    :return: Tuple of (data bytes, original width, original height, sampled width, sampled height)
    """
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
