"""
Main module
"""

import logging
import os
import sys
from typing import Literal

from fastapi import FastAPI
from h5grove.fastapi_utils import router, settings  # type: ignore
from starlette.middleware.cors import CORSMiddleware

stdout_handler = logging.StreamHandler(stream=sys.stdout)
logging.basicConfig(
    handlers=[stdout_handler],
    format="[%(asctime)s]-%(name)s-%(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logger.info("Starting Plotting Service")

ALLOWED_ORIGINS = ["*"]
CEPH_DIR = os.environ.get("CEPH_DIR", "/ceph")
logger.info("Setting ceph directory to %s", CEPH_DIR)
settings.base_dir = os.path.abspath(CEPH_DIR)


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def get() -> Literal["ok"]:
    """
    Health check endpoint
    \f
    :return: "ok"
    """
    return "ok"


app.include_router(router)
