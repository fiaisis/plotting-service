import shutil
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

import pytest
from fastapi import HTTPException

from plotting_service.utils import (
    find_experiment_number,
    find_file_experiment_number,
    find_file_instrument,
    find_file_user_number,
    safe_check_filepath,
)

CEPH_DIR = Path(TemporaryDirectory().name)


@pytest.fixture(autouse=True)
def _setup_and_clean_temp_dir():
    CEPH_DIR.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(CEPH_DIR)


@pytest.mark.parametrize(
    ("filepath_to_check", "result"),
    [
        (Path(CEPH_DIR) / "good" / "path" / "here" / "file.txt", True),
        (Path(CEPH_DIR) / "bad" / "path" / "here" / "file.txt", False),
        (Path(CEPH_DIR) / ".." / ".." / ".." / "file.txt", False),
    ],
)
def test_safe_check_filepath(filepath_to_check: Path, result: bool):
    if result:
        filepath_to_check.parent.mkdir(parents=True, exist_ok=True)
        filepath_to_check.write_text("Hello World!")
        safe_check_filepath(filepath_to_check, str(CEPH_DIR))
    else:
        with pytest.raises((HTTPException, FileNotFoundError)):
            safe_check_filepath(filepath_to_check, str(CEPH_DIR))


def test_find_instrument_most_likely_file():
    with TemporaryDirectory() as tmpdir:
        instrument_name = "FUN_INST"
        experiment_number = 1231234
        filename = "MAR1912991240_asa_dasd_123.nxspe"
        path = Path(tmpdir) / instrument_name / "RBNumber" / f"RB{experiment_number}" / "autoreduced" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Hello World!")

        found_file = find_file_instrument(tmpdir, instrument_name, experiment_number, filename)

        assert found_file == path


@pytest.mark.parametrize(
    ("find_file_method", "method_inputs", "path_to_make"),
    [
        (
            find_file_instrument,
            {
                "ceph_dir": CEPH_DIR,
                "instrument": "FUN_INST",
                "experiment_number": 1231234,
                "filename": "MAR1912991240_asa_dasd_123.nxspe",
            },
            CEPH_DIR / "FUN_INST" / "RBNumber" / "RB1231234" / "autoreduced" / "MAR1912991240_asa_dasd_123.nxspe",
        ),
        (
            find_file_experiment_number,
            {"ceph_dir": CEPH_DIR, "experiment_number": 1231234, "filename": "MAR1912991240_asa_dasd_123.nxspe"},
            CEPH_DIR / "GENERIC" / "autoreduce" / "ExperimentNumbers" / "1231234" / "MAR1912991240_asa_dasd_123.nxspe",
        ),
        (
            find_file_user_number,
            {"ceph_dir": CEPH_DIR, "user_number": 1231234, "filename": "MAR1912991240_asa_dasd_123.nxspe"},
            CEPH_DIR / "GENERIC" / "autoreduce" / "UserNumbers" / "1231234" / "MAR1912991240_asa_dasd_123.nxspe",
        ),
    ],
)
def test_find_file_method_in_a_dir(find_file_method: Callable, method_inputs: dict[str, Any], path_to_make: Path):
    with TemporaryDirectory() as tmpdir:
        instrument_name = "FUN_INST"
        experiment_number = 1231234
        filename = "MAR1912991240_asa_dasd_123.nxspe"
        path = (
            Path(tmpdir)
            / instrument_name
            / "RBNumber"
            / f"RB{experiment_number}"
            / "autoreduced"
            / "run-123141"
            / filename
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Hello World!")

        found_file = find_file_instrument(tmpdir, instrument_name, experiment_number, filename)

        assert found_file == path


@pytest.mark.parametrize(
    ("find_file_method", "method_inputs", "path_to_make"),
    [
        (
            find_file_instrument,
            {
                "ceph_dir": CEPH_DIR,
                "instrument": "FUN_INST",
                "experiment_number": 1231234,
                "filename": "MAR1912991240_asa_dasd_123.nxspe",
            },
            CEPH_DIR / "FUN_INST" / "RBNumber" / "RB1231234" / "autoreduced" / "MAR1912991240_asa_dasd_123.nxspe",
        ),
        (
            find_file_experiment_number,
            {"ceph_dir": CEPH_DIR, "experiment_number": 1231234, "filename": "MAR1912991240_asa_dasd_123.nxspe"},
            CEPH_DIR / "GENERIC" / "autoreduce" / "ExperimentNumbers" / "1231234" / "MAR1912991240_asa_dasd_123.nxspe",
        ),
        (
            find_file_user_number,
            {"ceph_dir": CEPH_DIR, "user_number": 1231234, "filename": "MAR1912991240_asa_dasd_123.nxspe"},
            CEPH_DIR / "GENERIC" / "autoreduce" / "UserNumbers" / "1231234" / "MAR1912991240_asa_dasd_123.nxspe",
        ),
    ],
)
def test_find_file_method_when_failed(find_file_method: Callable, method_inputs: dict[str, Any], path_to_make: Path):
    path_to_make.parent.mkdir(parents=True, exist_ok=True)

    found_file = find_file_method(**method_inputs)

    assert found_file is None


@pytest.mark.parametrize(
    ("find_file_method", "method_inputs"),
    [
        (find_file_instrument, {CEPH_DIR, "~/.ssh", "id_rsa", "MAR1912991240_asa_dasd_123.nxspe"}),
        (find_file_experiment_number, {CEPH_DIR, "~/.ssh", "id_rsa"}),
        (find_file_user_number, {CEPH_DIR, "~/.ssh", "id_rsa"}),
    ],
)
def test_find_file_methods_does_not_allow_path_injection(find_file_method: Callable, method_inputs: dict[str, Any]):
    with pytest.raises(HTTPException):
        find_file_method(*method_inputs)


def test_find_experiment_number_text():
    request = mock.MagicMock()
    experiment_number = 1245
    request.url.path = f"/text/instrument/LOQ/experiment_number/{experiment_number}"

    assert find_experiment_number(request) == experiment_number


def test_find_experiment_number_find_file():
    request = mock.MagicMock()
    experiment_number = 1245
    request.url.path = f"/find_file/instrument/LOQ/experiment_number/{experiment_number}"

    assert find_experiment_number(request) == experiment_number


def test_find_experiment_number_other():
    request = mock.MagicMock()
    experiment_number = 1245
    path = f"/meta/?file=LOQ%2FRBNumber%2FRB{experiment_number}%2Fautoreduced%2Frun-110754%2F110754.h5&path=%2F"
    request.url.query = path
    request.url.path = path

    assert find_experiment_number(request) == experiment_number
