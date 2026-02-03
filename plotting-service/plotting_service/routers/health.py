import os
import typing
from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, HTTPException

CEPH_DIR = os.environ.get("CEPH_DIR", "/ceph")

HealthRouter = APIRouter()

@HealthRouter.get("/healthz")
async def get() -> typing.Literal["ok"]:
    """Health check endpoint :return: "ok"."""
    try:
        with Path(f"{CEPH_DIR}/GENERIC/autoreduce/healthy_file.txt").open("r") as fle:
            lines = fle.readlines()
            if lines[0] != "This is a healthy file! You have read it correctly!\n":
                raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE)
        return "ok"
    except:  # noqa: E722
        raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE) from None
