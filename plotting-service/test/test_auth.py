from unittest.mock import patch

import pytest

from plotting_service.auth import User, get_experiments_for_user, get_user_from_token
from plotting_service.exceptions import AuthError

TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"  # noqa: S105
    ".eyJ1c2VybnVtYmVyIjoxMjM0LCJyb2xlIjoidXNlciIsInVzZXJuYW1lIjoiZm9vIiwiZXhwIjoyMTUxMzA1MzA0fQ"
    ".z7qVg2foW61rjYiKXp0Jw_cb5YkbWY-JoNG8GUVo2SY"
)


@patch("plotting_service.auth.requests.get")
def test_get_experiment_for_user(mock_get):
    mock_get.return_value.status_code = HTTPStatus.OK
    mock_get.return_value.json.return_value = [1234]

    exp_numbs = get_experiments_for_user(user=User(user_number=123, role="user"))
    assert exp_numbs == [1234]


@patch("plotting_service.auth.requests.get")
def test_get_experiments_for_user_non_200_status(mock_get):
    mock_get.return_value.status_code = HTTPStatus.FORBIDDEN

    with pytest.raises(RuntimeError):
        get_experiments_for_user(user=User(user_number=123, role="user"))


def test_get_user_from_token():
    user = get_user_from_token(TOKEN)
    expected_user_number = 1234
    assert user.user_number == expected_user_number
    assert user.role == "user"


def test_get_user_from_token_invalid_token():
    with pytest.raises(AuthError):
        get_user_from_token("foo")
