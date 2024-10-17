from pathlib import Path
from tempfile import TemporaryDirectory

from plotting_service.utils import find_file


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
        path = Path(tmpdir) / instrument_name / "RBNumber" / f"RB{experiment_number}" / "autoreduced" / "run-123141"/ filename
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
