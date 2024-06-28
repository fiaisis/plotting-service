"""
Auth functionality
"""

import logging
import os
from dataclasses import dataclass
from http import HTTPStatus
from typing import Literal

import jwt
import requests
from jwt import PyJWTError

from plotting_service.exceptions import AuthError

JWT_SECRET = os.environ.get("JWT_SECRET", "shh")
FIA_AUTH_URL = os.environ.get("FIA_AUTH_URL")
FIA_AUTH_API_KEY = os.environ.get("FIA_AUTH_API_KEY")

logger = logging.getLogger(__name__)


@dataclass
class User:
    """
    Simple dataclass for the token attached user
    """

    user_number: int
    role: Literal["staff"] | Literal["user"]


def get_user_from_token(token: str) -> User:
    """
    Given a jwt token, return the user, will raise if token is not valid
    :param token: the jwt token to check
    :return: The user
    """
    try:
        logger.info("Getting user from token")
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_signature": True, "verify_exp": True},
        )
        user = User(user_number=payload["usernumber"], role=payload["role"])
        logger.info("Successfuly retrieved user")
        return user
    except PyJWTError as exc:
        logger.exception("Failed to get user from token")
        raise AuthError() from exc


def get_experiments_for_user(user: User) -> list[int]:
    """
    Given a user, return the experiment (RB) numbers associated with that user
    :param user: The user to get for
    :return: The users experiment numbers
    """
    response = requests.get(
        f"{FIA_AUTH_URL}/experiment?user_number={user.user_number}",
        headers={"Authorization": f"Bearer {FIA_AUTH_API_KEY}"},
        timeout=30,
    )
    if response.status_code == HTTPStatus.OK:
        experiment_numbers: list[int] = response.json()
        return experiment_numbers
    raise RuntimeError("Could not contact the auth api")
