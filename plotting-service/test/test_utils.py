from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest
from fastapi import HTTPException

from plotting_service.utils import find_experiment_number, find_file


def test_find_most_likely_file():
    with TemporaryDirectory() as tmpdir:
        instrument_name = "FUN_INST"
        experiment_number = 1231234
        filename = "MAR1912991240_asa_dasd_123.nxspe"
        path = Path(tmpdir) / instrument_name / "RBNumber" / f"RB{experiment_number}" / "autoreduced" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Hello World!")

        found_file = find_file(tmpdir, instrument_name, experiment_number, filename)

        assert found_file == path


def test_find_file_in_a_dir():
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

        found_file = find_file(tmpdir, instrument_name, experiment_number, filename)

        assert found_file == path


def test_find_file_when_failed():
    with TemporaryDirectory() as tmpdir:
        instrument_name = "FUN_INST"
        experiment_number = 1231234
        filename = "MAR1912991240_asa_dasd_123.nxspe"
        path = Path(tmpdir) / instrument_name / "RBNumber" / f"RB{experiment_number}" / "autoreduced" / filename
        path.parent.mkdir(parents=True, exist_ok=True)

        found_file = find_file(tmpdir, instrument_name, experiment_number, filename)

        assert found_file is None


def test_find_file_does_not_allow_path_injection():
    with TemporaryDirectory() as tmpdir:
        instrument_name = "~/.ssh"
        experiment_number = "id_rsa"
        filename = "MAR1912991240_asa_dasd_123.nxspe"

        with pytest.raises(HTTPException):
            find_file(tmpdir, instrument_name, experiment_number, filename)


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
