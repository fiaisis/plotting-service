from collections.abc import Callable, Iterator
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

import pytest
import requests

HEALTHY_FILE_CONTENT = "This is a healthy file! You have read it correctly!\n"
SAMPLE_SOURCE = (
    Path(__file__).resolve().parent
    / "test_ceph"
    / "MARI"
    / "RBNumber"
    / "RB20024"
    / "autoreduced"
    / "MAR29531_10.5meV_sa.nxspe"
)
SAMPLE_RELATIVE_PATH = Path("MARI/RBNumber/RB20024/autoreduced/MAR29531_10.5meV_sa.nxs")


def _wait_for_server_ready(process: subprocess.Popen[str], base_url: str, log_path: Path) -> None:
    deadline = time.monotonic() + 15
    last_error = "server did not start"

    while time.monotonic() < deadline:
        if process.poll() is not None:
            last_error = f"uvicorn exited with code {process.returncode}"
            break

        try:
            response = requests.get(f"{base_url}/healthz", timeout=0.5)
            if response.status_code == 200:
                return
            last_error = f"{response.status_code}: {response.text}"
        except requests.RequestException as exc:
            last_error = str(exc)

        time.sleep(0.25)

    logs = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    raise AssertionError(f"failed to start test server ({last_error})\n{logs}")


@pytest.fixture(scope="module")
def e2e_server(unused_tcp_port_factory: Callable[[], int]) -> Iterator[dict[str, str]]:
    repo_root = Path(__file__).resolve().parents[1]
    ceph_dir = repo_root / f"ceph-e2e-{uuid.uuid4().hex}"
    ceph_dir.mkdir()
    healthy_file = ceph_dir / "GENERIC" / "autoreduce" / "healthy_file.txt"
    healthy_file.parent.mkdir(parents=True)
    healthy_file.write_text(HEALTHY_FILE_CONTENT, encoding="utf-8")

    sample_target = ceph_dir / SAMPLE_RELATIVE_PATH
    sample_target.parent.mkdir(parents=True)
    shutil.copy2(SAMPLE_SOURCE, sample_target)

    port = unused_tcp_port_factory()
    base_url = f"http://127.0.0.1:{port}"
    log_path = ceph_dir / "uvicorn.log"
    env = os.environ.copy()
    env["CEPH_DIR"] = str(ceph_dir)
    env["DEV_MODE"] = "True"
    env["PYTHONUNBUFFERED"] = "1"

    with log_path.open("w", encoding="utf-8") as server_log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "plotting_service.plotting_api:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=repo_root,
            env=env,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            _wait_for_server_ready(process, base_url, log_path)
            yield {"base_url": base_url, "file": SAMPLE_RELATIVE_PATH.as_posix()}
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            shutil.rmtree(ceph_dir, ignore_errors=True)


def test_healthz_returns_ok_over_http(e2e_server: dict[str, str]):
    response = requests.get(f"{e2e_server['base_url']}/healthz", timeout=5)

    assert response.status_code == 200
    assert response.json() == "ok"


def test_meta_returns_dataset_structure_for_nxs_file(e2e_server: dict[str, str]):
    response = requests.get(
        f"{e2e_server['base_url']}/meta/",
        params={"file": e2e_server["file"], "path": "/ws_out/data"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    children = {child["name"]: child for child in payload["children"]}

    assert payload["kind"] == "group"
    assert children["data"]["kind"] == "dataset"
    assert children["data"]["shape"] == [285, 640]


def test_data_returns_a_small_numeric_slice_over_http(e2e_server: dict[str, str]):
    response = requests.get(
        f"{e2e_server['base_url']}/data/",
        params={"file": e2e_server["file"], "path": "/ws_out/data/energy", "selection": "0:3"},
        timeout=5,
    )

    assert response.status_code == 200
    assert response.json() == pytest.approx([-8.4, -8.37375, -8.3475])
