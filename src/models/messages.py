from datetime import datetime
from typing import Literal

from pydantic import Field
from sanic_ext.extensions.openapi import openapi

from src.utils.base import BaseList, BaseModel


class Message(BaseModel):
    content: str
    type: Literal['message', 'announcement']
    repetitions: int = 1
    interval_seconds: int = 1

class DiscordMessage(BaseModel):
    content: str
    sender: str
