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

    async def


class BedrockServer:
    ...