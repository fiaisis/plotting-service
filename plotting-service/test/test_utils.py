from unittest import mock

from plotting_service.utils import find_experiment_number


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
