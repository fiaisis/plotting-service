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
from plotting_service.plotting_api import check_permissions
from plotting_service.routers import imat
from plotting_service.services.image_service import convert_image_to_rgb_array

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
    request.url.path = "/data"
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
    request.url.path = "/data"
    request.url.query = ""
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
    request.url.path = "/data"
    request.headers.get("Authorization").split.return_value = [None, "bad_token"]
    call_next = AwaitableNonAsyncMagicMock()

    with pytest.raises(HTTPException):
        await check_permissions(request, call_next)

    call_next.assert_not_called()


def testconvert_image_to_rgb_array_returns_data_and_metadata(tmp_path):
    """Ensure images convert to RGB data without altering size when no
    downsampling occurs."""
    image_path = tmp_path / "sample_image.tiff"
    image = Image.new("L", (10, 20), color=128)
    image.save(image_path, format="TIFF")
    image.close()

    data, orig_w, orig_h, sampled_w, sampled_h = convert_image_to_rgb_array(image_path, 1)

    assert (orig_w, orig_h) == (10, 20)
    assert (sampled_w, sampled_h) == (10, 20)
    assert len(data) == sampled_w * sampled_h * 3

    with Image.open(image_path) as original:
        expected = original.convert("RGB")
    expected_bytes = list(expected.tobytes())
    expected.close()

    assert data == expected_bytes


def testconvert_image_to_rgb_array_downsamples(tmp_path):
    """Verify the helper downsamples dimensions and reports updated metadata
    correctly."""
    image_path = tmp_path / "sample_downsample_image.tiff"
    image = Image.new("L", (16, 8))
    for x in range(16):
        for y in range(8):
            image.putpixel((x, y), min(255, x * 16 + y * 8))
    image.save(image_path, format="TIFF")
    image.close()

    data, orig_w, orig_h, sampled_w, sampled_h = convert_image_to_rgb_array(image_path, 4)

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
    monkeypatch.setattr(imat, "IMAT_DIR", tmp_path)
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


def test_list_imat_images(tmp_path, monkeypatch):
    """Verify that /imat/list-images correctly filters and sorts image files."""
    monkeypatch.setattr(imat, "CEPH_DIR", str(tmp_path))

    # Create test directory
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    (data_dir / "image2.tiff").touch()
    (data_dir / "image1.tif").touch()
    (data_dir / "not_an_image.txt").touch()

    client = TestClient(plotting_api.app)
    response = client.get(
        "/imat/list-images",
        params={"path": "test_data"},
        headers={"Authorization": "Bearer foo"}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == ["image1.tif", "image2.tiff"]


def test_list_imat_images_not_found(tmp_path, monkeypatch):
    """Ensure 404 is returned when the requested directory does not exist."""
    monkeypatch.setattr(imat, "CEPH_DIR", str(tmp_path))

    client = TestClient(plotting_api.app)
    response = client.get(
        "/imat/list-images",
        params={"path": "non_existent"},
        headers={"Authorization": "Bearer foo"}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_list_imat_images_forbidden(tmp_path, monkeypatch):
    """Verify that path traversal attempts are blocked with 403 Forbidden."""
    monkeypatch.setattr(imat, "CEPH_DIR", str(tmp_path))

    client = TestClient(plotting_api.app)
    # safe_check_filepath should block this
    response = client.get(
        "/imat/list-images",
        params={"path": "../.."},
        headers={"Authorization": "Bearer foo"}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_get_imat_image(tmp_path, monkeypatch):
    """Ensure /imat/image returns raw binary data and correct metadata headers."""
    monkeypatch.setattr(imat, "CEPH_DIR", str(tmp_path))

    # Create a tiny 16-bit TIFF (4x4, all 1000)
    image_path = tmp_path / "test.tif"
    image = Image.new("I;16", (4, 4), color=1000)
    image.save(image_path, format="TIFF")
    image.close()

    client = TestClient(plotting_api.app)
    response = client.get(
        "/imat/image",
        params={"path": "test.tif"},
        headers={"Authorization": "Bearer foo"}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.headers["X-Image-Width"] == "4"
    assert response.headers["X-Image-Height"] == "4"
    assert response.headers["X-Original-Width"] == "4"
    assert response.headers["X-Original-Height"] == "4"
    assert response.headers["X-Downsample-Factor"] == "1"
    assert response.content == Image.open(image_path).tobytes()
    assert response.headers["Content-Type"] == "application/octet-stream"


def test_get_imat_image_downsampled(tmp_path, monkeypatch):
    """Verify that downsampling works and headers reflect the sampled dimensions."""
    monkeypatch.setattr(imat, "CEPH_DIR", str(tmp_path))

    image_path = tmp_path / "test.tif"
    image = Image.new("I;16", (8, 4), color=1000)
    image.save(image_path, format="TIFF")
    image.close()

    client = TestClient(plotting_api.app)
    response = client.get(
        "/imat/image",
        params={"path": "test.tif", "downsample_factor": 2},
        headers={"Authorization": "Bearer foo"}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.headers["X-Image-Width"] == "4"
    assert response.headers["X-Image-Height"] == "2"
    assert response.headers["X-Original-Width"] == "8"
    assert response.headers["X-Original-Height"] == "4"


def test_get_latest_imat_image_no_rb_folders(tmp_path, monkeypatch):
    """Ensure 404 is returned if no RB folders are present in the IMAT directory."""
    monkeypatch.setattr(imat, "IMAT_DIR", tmp_path)

    client = TestClient(plotting_api.app)
    response = client.get(
        "/imat/latest-image",
        headers={"Authorization": "Bearer foo"}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "No RB folders" in response.json()["detail"]


def test_get_imat_image_not_found(tmp_path, monkeypatch):
    """Ensure /imat/image returns 404 for a missing file."""
    monkeypatch.setattr(imat, "CEPH_DIR", str(tmp_path))

    client = TestClient(plotting_api.app)
    response = client.get(
        "/imat/image",
        params={"path": "not_there.tif"},
        headers={"Authorization": "Bearer foo"}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_latest_imat_image_no_images_in_rb(tmp_path, monkeypatch):
    """Ensure 404 is returned if RB folders exist but contain no valid image files."""
    monkeypatch.setattr(imat, "IMAT_DIR", tmp_path)
    (tmp_path / "RB1234").mkdir()

    client = TestClient(plotting_api.app)
    response = client.get(
        "/imat/latest-image",
        headers={"Authorization": "Bearer foo"}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "No images found" in response.json()["detail"]


def test_get_imat_image_internal_error(tmp_path, monkeypatch):
    """Verify that an exception during image processing returns a 500 error."""
    monkeypatch.setattr(imat, "CEPH_DIR", str(tmp_path))
    (tmp_path / "corrupt.tif").touch()

    client = TestClient(plotting_api.app)
    with mock.patch("PIL.Image.open", side_effect=Exception("Simulated failure")):
        response = client.get(
            "/imat/image",
            params={"path": "corrupt.tif"},
            headers={"Authorization": "Bearer foo"}
        )

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Unable to process image" in response.json()["detail"]


def test_get_latest_imat_image_conversion_error(tmp_path, monkeypatch):
    """Verify that an error during RB latest image conversion returns a 500 error."""
    monkeypatch.setattr(imat, "IMAT_DIR", tmp_path)
    rb_dir = tmp_path / "RB1234"
    rb_dir.mkdir()
    (rb_dir / "test.tif").touch()

    client = TestClient(plotting_api.app)
    with mock.patch(
        "plotting_service.routers.imat.convert_image_to_rgb_array", side_effect=Exception("Conversion failed")
    ):
        response = client.get(
            "/imat/latest-image",
            params={"downsample_factor": 1},
            headers={"Authorization": "Bearer foo"}
        )

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Unable to convert IMAT image" in response.json()["detail"]
