import asyncio
import json
from typing import AsyncIterable
import shutil
import psutil
from datetime import datetime
import os

import httpx
from httpx import AsyncClient
from bs4 import BeautifulSoup
from jproperties import Properties
import re

from copy import deepcopy

def log(name: str, message: str):
    print(f"[{datetime.now()}] [{name.upper()}] {message}")


class NexusCore:
    def __init__(self):
        self.version = 'v5.0'
        self.server: BedrockServer = BedrockServer()
        self.system_logs: list[dict] = []
        self.config = json.load(open('bdsconfig.json', 'r'))

        print(self.config['title'])
        log("core", f"NexusCore Version: {self.version}")
        log("core", "Starting up NexusCore...")
        self.nexus_looper()

    async def system_log_loop(self):
        log("looper", "Starting NexusCore System Logger...")

    async def backup_loop(self):
        log("core", "Starting NexusCore Backup Handler...")

    async def restart_loop(self):
        log("core", "Starting NexusCore Restart Handler...")

    async def crash_loop(self):
        log("core", "Starting NexusCore Crash Handler...")

    async def nexus_looper(self):
        log("core", "Starting NexusCore Looper...")
        await asyncio.gather(asyncio.create_task(coro=self.system_log_loop(),
                                                 name='NexusCore System Logger'),
                             asyncio.create_task(coro=self.backup_loop(),
                                                 name='NexusCore Backup Handler'),
                             asyncio.create_task(coro=self.restart_loop(),
                                                 name='NexusCore Restart Handler'),
                             asyncio.create_task(coro=self.crash_loop(),
                                                 name='NexusCore Crash Handler')
                             )
        log("core", "NexusCore Looper started successfully")

    async def update_checker(self):
        ...

    async def start_server(self):
        ...

    async def stop_server(self):
        ...



class BedrockServer:
    """
    All possible statuses:
    not_running: The server is not running. This is only set during class initialization.

    """
    def __init__(self):
        self.server: asyncio.subprocess.Process
        self.start: datetime = datetime.now().replace(microsecond=0)
        self.status: str = 'not_running'
        self.config: dict = json.load(open("bdsconfig.json", "r"))
        self.version: str = self.config['last_saved_version']
        self.discord_guild_id: int = self.config['discord_guild_link']
        self.process_id: int

        prop_file = Properties()
        prop_file.load(open("server/1.19.1/server.properties", 'rb'))
        self.server_properties = prop_file.properties