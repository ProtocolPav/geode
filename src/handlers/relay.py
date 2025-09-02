import asyncio
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import httpx
from sanic.log import logger, Colors

from src.handlers.config import ConfigHandler
from src.cloud_services.base import get_cloud_service

class RelayHandler:
    @classmethod
    async def relay(cls,
                    message_type: Literal['start', 'stop', 'crash', 'other'],
                    embed_title: str,
                    embed_content: str,
                    name: Optional[str] = "Geode"):
        async with httpx.AsyncClient() as client:
            await client.post('http://nexuscore:8000/api/v0.2/events/relay',
                              json={'type': message_type,
                                    'content': '',
                                    'embed_title': embed_title,
                                    'embed_content': embed_content,
                                    'name': name})

    @classmethod
    async def relay_start(cls):
        await cls.relay('start',
                        "Server Start",
                        "The server has started.\n\n"
                                     "-# *Powered by **Geode***")

    @classmethod
    async def relay_stop(cls):
        await cls.relay('stop',
                        "Server Stop",
                        "The server has stopped. Be patient, and it will be back up soon!\n\n"
                        "-# *Powered by **Geode***")

    @classmethod
    async def relay_message(cls, content: str):
        await cls.relay('other',
                        "Server Message",
                        content)

    @classmethod
    async def relay_announcement(cls, content: str):
        await cls.relay('other',
                        "Server Announcement",
                        content)