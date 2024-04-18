"""
Main module
"""

import logging
import sys

from fastapi import FastAPI

from plotting_service.router import ROUTER

stdout_handler = logging.StreamHandler(stream=sys.stdout)
logging.basicConfig(
    handlers=[stdout_handler],
    format="[%(asctime)s]-%(name)s-%(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


app = FastAPI()

app.include_router(ROUTER)
