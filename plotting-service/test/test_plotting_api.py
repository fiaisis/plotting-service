import os
from collections.abc import Iterator
from io import BytesIO
from typing import Any
from unittest import mock

import pytest
from fastapi.exceptions import HTTPException
from PIL import Image

from plotting_service.plotting_api import _convert_image_to_png, check_permissions

USER_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"  # noqa: S105
    ".eyJ1c2VybnVtYmVyIjoxMjM0LCJyb2xlIjoidXNlciIsInVzZXJuYW1lIjoiZm9vIiwiZXhwIjoyMTUxMzA1MzA0fQ"
    ".z7qVg2foW61rjYiKXp0Jw_cb5YkbWY-JoNG8GUVo2SY"
)
STAFF_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."  # noqa: S105
    "eyJ1c2VybnVtYmVyIjoxMjM0LCJyb2xlIjoic3RhZmYiLCJ1c2VybmFtZSI6ImZvbyIsImV4cCI6NDg3MjQ2ODk4M30."
    "-ktYEwdUfg5_PmUocmrAonZ6lwPJdcMoklWnVME1wLE"
)


class AwaitableNonAsyncMagicMock(mock.MagicMock):
    def __await__(self) -> Iterator[Any]:
        return iter([])


@pytest.fixture(autouse=True)
def api_key_setter():
    os.environ["API_KEY"] = "foo"
    yield "api_key_setter"
    os.environ.pop("API_KEY")


@pytest.mark.asyncio
async def test_check_permissions_api_key():
    request = mock.MagicMock()
    request.headers.get("Authorization").split.return_value = [None, "foo"]
    call_next = AwaitableNonAsyncMagicMock()

    await check_permissions(request, call_next)

    call_next.assert_called_once_with(request)


@pytest.mark.asyncio
async def test_check_permissions_api_key_failed():
    os.environ["API_KEY"] = "ActuallyADecentAPIKey"
    request = mock.MagicMock()
    request.headers.get("Authorization").split.return_value = [None, "foo"]
    call_next = AwaitableNonAsyncMagicMock()

    with pytest.raises(HTTPException):
        await check_permissions(request, call_next)

    call_next.assert_not_called()


@pytest.mark.asyncio
async def test_check_permissions_token_user():
    request = mock.MagicMock()
    request.url.path = "/data?path=/"
    request.headers.get("Authorization").split.return_value = [None, USER_TOKEN]
    call_next = AwaitableNonAsyncMagicMock()
    experiment_number = str(mock.MagicMock())

    with (
        mock.patch("plotting_service.plotting_api.find_experiment_number") as experiment_number_mock,
        mock.patch("plotting_service.plotting_api.get_experiments_for_user") as get_experiments_for_user_mock,
    ):
        experiment_number_mock.return_value = experiment_number
        get_experiments_for_user_mock.return_value = [experiment_number]
        await check_permissions(request, call_next)

    call_next.assert_called_once_with(request)


@pytest.mark.asyncio
async def test_check_permissions_token_user_failed_no_perms():
    request = mock.MagicMock()
    request.headers.get("Authorization").split.return_value = [None, USER_TOKEN]
    call_next = AwaitableNonAsyncMagicMock()

    with pytest.raises(HTTPException):
        await check_permissions(request, call_next)

    call_next.assert_not_called()


@pytest.mark.asyncio
async def test_check_permissions_token_staff():
    request = mock.MagicMock()
    request.headers.get("Authorization").split.return_value = [None, STAFF_TOKEN]
    call_next = AwaitableNonAsyncMagicMock()

    await check_permissions(request, call_next)

    call_next.assert_called_once_with(request)


@pytest.mark.asyncio
async def test_check_permissions_token_failed_bad_token():
    request = mock.MagicMock()
    request.headers.get("Authorization").split.return_value = [None, "bad_token"]
    call_next = AwaitableNonAsyncMagicMock()

    with pytest.raises(HTTPException):
        await check_permissions(request, call_next)

    call_next.assert_not_called()


def test_convert_image_to_png_returns_png_and_metadata(tmp_path):
    """
    Ensure images convert to PNG without altering size or luminance range when
    no downsampling occurs.
    """
    image_path = tmp_path / "sample_image.tiff"
    image = Image.new("L", (10, 20), color=128)
    image.save(image_path, format="TIFF")
    image.close()

    buffer, orig_w, orig_h, sampled_w, sampled_h, min_val, max_val = _convert_image_to_png(image_path, 1)

    assert (orig_w, orig_h) == (10, 20)
    assert (sampled_w, sampled_h) == (10, 20)

    converted = Image.open(BytesIO(buffer.getvalue()))
    luminance = converted.convert("L")
    extrema = luminance.getextrema()

    assert extrema == (128, 128)
    assert (min_val, max_val) == extrema
    assert converted.format == "PNG"
    assert converted.mode == "RGBA"
    assert converted.size == (10, 20)
    converted.close()


def test_convert_image_to_png_downsamples(tmp_path):
    """
    Verify the helper downsamples dimensions and reports updated metadata
    correctly.
    """
    image_path = tmp_path / "sample_downsample_image.tiff"
    image = Image.new("L", (16, 8))
    for x in range(16):
        for y in range(8):
            image.putpixel((x, y), min(255, x * 16 + y * 8))
    image.save(image_path, format="TIFF")
    image.close()

    buffer, orig_w, orig_h, sampled_w, sampled_h, min_val, max_val = _convert_image_to_png(image_path, 4)

    assert (orig_w, orig_h) == (16, 8)
    assert (sampled_w, sampled_h) == (4, 2)

    converted = Image.open(BytesIO(buffer.getvalue()))
    assert converted.size == (4, 2)

    luminance = converted.convert("L")
    extrema = luminance.getextrema()
    assert extrema is not None
    assert (min_val, max_val) == extrema
    converted.close()
