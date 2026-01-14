import os
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any
from unittest import mock

import pytest
from fastapi.exceptions import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from plotting_service import plotting_api
from plotting_service.plotting_api import _convert_image_to_rgb_array, check_permissions

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


def test_convert_image_to_rgb_array_returns_data_and_metadata(tmp_path):
    """Ensure images convert to RGB data without altering size when no
    downsampling occurs."""
    image_path = tmp_path / "sample_image.tiff"
    image = Image.new("L", (10, 20), color=128)
    image.save(image_path, format="TIFF")
    image.close()

    data, orig_w, orig_h, sampled_w, sampled_h = _convert_image_to_rgb_array(image_path, 1)

    assert (orig_w, orig_h) == (10, 20)
    assert (sampled_w, sampled_h) == (10, 20)
    assert len(data) == sampled_w * sampled_h * 3

    with Image.open(image_path) as original:
        expected = original.convert("RGB")
    expected_bytes = list(expected.tobytes())
    expected.close()

    assert data == expected_bytes


def test_convert_image_to_rgb_array_downsamples(tmp_path):
    """Verify the helper downsamples dimensions and reports updated metadata
    correctly."""
    image_path = tmp_path / "sample_downsample_image.tiff"
    image = Image.new("L", (16, 8))
    for x in range(16):
        for y in range(8):
            image.putpixel((x, y), min(255, x * 16 + y * 8))
    image.save(image_path, format="TIFF")
    image.close()

    data, orig_w, orig_h, sampled_w, sampled_h = _convert_image_to_rgb_array(image_path, 4)

    assert (orig_w, orig_h) == (16, 8)
    assert (sampled_w, sampled_h) == (4, 2)
    assert len(data) == sampled_w * sampled_h * 3

    with Image.open(image_path) as original:
        expected = original.convert("RGB").resize((4, 2), Image.Resampling.LANCZOS)
    expected_bytes = list(expected.tobytes())
    expected.close()

    assert data == expected_bytes


def test_get_latest_imat_image_with_mock_rb_folder(tmp_path, monkeypatch):
    """End-to-end test of the /imat/latest-image endpoint which creates a
    sample RB folder with a TIFF image, then calls the endpoint to retrieve RGB
    data and verifies the returned payload."""
    # Point the IMAT directory at an isolated temp dir with a single RB folder
    monkeypatch.setattr(plotting_api, "IMAT_DIR", tmp_path)
    rb_dir = tmp_path / "RB1234"
    rb_dir.mkdir()

    # Build a tiny RGB 8-by-4 pixel TIFF
    image_path = rb_dir / "imat_sample.tiff"
    image = Image.new("RGB", (8, 4))
    for x in range(image.width):
        for y in range(image.height):
            image.putpixel((x, y), (x * 20 % 256, y * 40 % 256, (x + y) * 15 % 256))
    image.save(image_path, format="TIFF")
    image.close()

    with Image.open(image_path) as original:
        expected = original.convert("RGB").resize((4, 2), Image.Resampling.LANCZOS)
    expected_bytes = list(expected.tobytes())
    expected.close()

    # Call the endpoint and verify the downsampled RGB payload
    client = TestClient(plotting_api.app)
    response = client.get(
        "/imat/latest-image", params={"downsample_factor": 2}, headers={"Authorization": "Bearer foo"}
    )
    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["originalWidth"] == 8  # noqa: PLR2004
    assert payload["originalHeight"] == 4  # noqa: PLR2004
    assert payload["sampledWidth"] == 4  # noqa: PLR2004
    assert payload["sampledHeight"] == 2  # noqa: PLR2004
    assert payload["shape"] == [2, 4, 3]
    assert payload["downsampleFactor"] == 2  # noqa: PLR2004
    assert payload["data"] == expected_bytes
