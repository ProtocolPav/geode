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
        version_file = Path('../server/version.geode')
        version = version_file.read_text()
        await cls.relay('start',
                        "Server Start",
                        f"The server has started. Running Minecraft Version **{version}**\n"
                                     "-# *Powered by **Geode***")

    @classmethod
    async def relay_stop(cls):
        await cls.relay('stop',
                        "Server Stop",
                        "The server has stopped. Be patient, and it will be back up soon!\n"
                        "-# *Powered by **Geode***")

    @classmethod
    async def relay_preemption(cls):
        await cls.relay('crash',
                        "Server Preemption Detected",
                        "The server is shutting down to keep your builds safe and prevent world corruption!\n"
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