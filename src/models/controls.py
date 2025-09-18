from datetime import datetime

from pydantic import Field
from sanic_ext.extensions.openapi import openapi

from src.utils.base import BaseList, BaseModel

class Command(BaseModel):
    command: str
