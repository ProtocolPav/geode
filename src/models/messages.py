from typing import Literal

from src.utils.base import BaseModel


class Message(BaseModel):
    content: str
    type: Literal['message', 'announcement']
    repetitions: int = 1
    interval_seconds: int = 1

class DiscordMessage(BaseModel):
    content: str
    sender: str
