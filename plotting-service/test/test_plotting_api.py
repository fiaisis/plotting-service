import os
from typing import Any, Iterator
from unittest import mock

import pytest
from fastapi.exceptions import HTTPException

from plotting_service.plotting_api import check_permissions

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

    with (mock.patch("plotting_service.plotting_api.find_experiment_number") as experiment_number_mock,
          mock.patch(
            "plotting_service.plotting_api.get_experiments_for_user") as get_experiments_for_user_mock):
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
