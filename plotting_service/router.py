"""
module containing main router defined routes
"""

from typing import Literal

from fastapi import APIRouter

ROUTER = APIRouter()


@ROUTER.get("/healthz")
async def get() -> Literal["ok"]:
    """
    Health check endpoint
    :return: "ok"
    """
    return "ok"
