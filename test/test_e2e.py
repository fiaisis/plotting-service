import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from http import HTTPStatus
from pathlib import Path

import h5py
import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
HEALTHY_FILE_CONTENT = "This is a healthy file! You have read it correctly!\n"
NEXUS_RELATIVE_PATH = "MARI/RBNumber/RB20024/autoreduced/sample.nxs"
NEXUS_DATASET_PATH = "/entry/data"
NEXUS_DATASET_VALUES = [[1, 2, 3], [4, 5, 6]]
REQUEST_TIMEOUT_SECONDS = 5
STARTUP_TIMEOUT_SECONDS = 15
STARTUP_POLL_SECONDS = 0.1
STARTUP_REQUEST_TIMEOUT_SECONDS = 0.5
SERVER_SHUTDOWN_TIMEOUT_SECONDS = 10


@pytest.fixture(scope="module")
def e2e_ceph_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    ceph_dir = tmp_path_factory.mktemp("ceph")

    health_file = ceph_dir / "GENERIC" / "autoreduce" / "healthy_file.txt"
    health_file.parent.mkdir(parents=True)
    health_file.write_text(HEALTHY_FILE_CONTENT, encoding="utf-8")

    nexus_file_path = ceph_dir / NEXUS_RELATIVE_PATH
    nexus_file_path.parent.mkdir(parents=True)

    with h5py.File(nexus_file_path, "w") as nexus_file:
        entry = nexus_file.create_group("entry")
        entry.attrs["NX_class"] = "NXentry"
        dataset = entry.create_dataset("data", data=NEXUS_DATASET_VALUES)
        dataset.attrs["units"] = "counts"

    return ceph_dir


@pytest.fixture(scope="module")
def live_server(e2e_ceph_dir: Path, unused_tcp_port_factory: Callable[[], int]) -> Iterator[str]:
    port = unused_tcp_port_factory()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update(
        {
            "CEPH_DIR": str(e2e_ceph_dir),
            "DEV_MODE": "True",
            "PYTHONUNBUFFERED": "1",
        }
    )

    process = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "plotting_service.plotting_api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_server(base_url, process)
        yield base_url
    finally:
        _stop_server(process)


def test_health_check_endpoint(live_server: str):
    response = requests.get(f"{live_server}/healthz", timeout=REQUEST_TIMEOUT_SECONDS)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == "ok"


def test_meta_endpoint_returns_nexus_dataset_metadata(live_server: str):
    response = requests.get(
        f"{live_server}/meta/",
        params={"file": NEXUS_RELATIVE_PATH, "path": NEXUS_DATASET_PATH},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    assert response.status_code == HTTPStatus.OK
    metadata = response.json()
    assert metadata["kind"] == "dataset"
    assert metadata["name"] == "data"
    assert metadata["shape"] == [2, 3]
    assert any(attribute["name"] == "units" for attribute in metadata["attributes"])


def test_data_endpoint_returns_nexus_dataset_values(live_server: str):
    response = requests.get(
        f"{live_server}/data/",
        params={"file": NEXUS_RELATIVE_PATH, "path": NEXUS_DATASET_PATH},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == NEXUS_DATASET_VALUES


def _wait_for_server(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    last_error = "server did not respond"

    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"Uvicorn exited before becoming ready.\n{_read_process_output(process)}")

        try:
            response = requests.get(f"{base_url}/healthz", timeout=STARTUP_REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            last_error = str(exc)
        else:
            if response.status_code == HTTPStatus.OK:
                return
            last_error = f"/healthz returned {response.status_code}: {response.text}"

        time.sleep(STARTUP_POLL_SECONDS)

    pytest.fail(f"Timed out waiting for Uvicorn at {base_url}: {last_error}")


def _stop_server(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()

    try:
        process.communicate(timeout=SERVER_SHUTDOWN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=SERVER_SHUTDOWN_TIMEOUT_SECONDS)


def _read_process_output(process: subprocess.Popen[str]) -> str:
    if process.stdout is None:
        return ""
    return process.stdout.read()
