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

import errors

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

    server: asyncio.subprocess.Process

    def __init__(self):
        self.start: datetime = datetime.now().replace(microsecond=0)
        self.status: str = 'not_running'
        self.config: dict = json.load(open("bdsconfig.json", "r"))
        self.version: str = self.config['last_saved_version']
        self.discord_guild_id: int = self.config['discord_guild_link']
        self.process_id: int = 0

        prop_file = Properties()
        prop_file.load(open("server/1.19.1/server.properties", 'rb'))
        self.server_properties = prop_file.properties

    def set_status(self, new_status: str):
        log('server', f'Status updated from {self.status} to {new_status}')
        self.status = new_status

    async def create_server(self, start_status: str = 'started_by_user'):
        self.server = await asyncio.create_subprocess_shell("cd server/1.19.1 && LD_LIBRARY_PATH=. ./bedrock_server",
                                                            stdin=asyncio.subprocess.PIPE,
                                                            stdout=asyncio.subprocess.PIPE,
                                                            stderr=asyncio.subprocess.STDOUT,
                                                            limit= 1024 * 512
                                                            )
        self.set_status(start_status)
        self.process_id = self.server.pid

        for key, val in self.server_properties.items():
            log('server info', f"{key}: {val}")

        server_tasks = [asyncio.create_task(coro=self.console_output(),
                                            name=f"[PID{self.process_id}] Minecraft Server Console Output")
                        ]

        try:
            await asyncio.gather(*server_tasks)

        except errors.ServerStopped as e:
            log('server', f'ServerStopped Exception raised! Canceling all running tasks...')

            for task in server_tasks:
                log('server', f'Canceling task {task.get_name()}')
                task.cancel()

            raise e

    async def player_event(self, gamertag: str, event: str):
        async with AsyncClient() as client:
            sent_successfully = False
            while not sent_successfully:
                try:
                    await client.post(f"http://thorny-wbs:8000/"
                                      f"<guild_id:{self.discord_guild_id}>/"
                                      f"<gamertag:{gamertag}>/{event}")
                    sent_successfully = True

                except httpx.TimeoutException:
                    log('server', f"TimeoutException raised while sending '{event}' event. Retrying in 30 seconds.")
                    await asyncio.sleep(30)

    async def initiate_backup(self, file_list: list[str]):
        path_to_worlds = 'server/1.19.1/worlds'
        path_to_backup = 'server/1.19.1/backup'
        daily_backup_hour = 16
        monthly_backup_day = 28
        world_name = self.server_properties["level-name"]
        s3_bucket = self.config['backup']['s3_bucket']

        file_date = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        os.makedirs(f'{path_to_backup}/{world_name} {file_date}/db')

        for file in file_list:
            file_path = file.split('/')
            file_to_copy = file_path[-1].split(':')[0]
            file_length = int(file_path[-1].split(':')[1])

            db = "db" if "db" in file_path else ""

            original_path = f"{path_to_worlds}/{world_name}/{db}/{file_to_copy}"
            destination_path = f"{path_to_backup}/{world_name} {file_date}/{db}/{file_to_copy}"

            shutil.copyfile(original_path, destination_path)

            with open(destination_path, 'a') as f:
                f.truncate(file_length)

        shutil.make_archive(f"{path_to_backup}/{world_name} {file_date}", 'zip',
                            f"{path_to_backup}/{world_name} {file_date}")
        shutil.rmtree(f"{path_to_backup}/{world_name} {file_date}")

        size = os.path.getsize(f"{path_to_backup}/{world_name} {file_date}.zip")

        log('backup', 'Finished backup')
        log('backup', f'This backup is {round(size / 1000 / 1000, 2)}MB')
        log('backup', f'Beginning upload to s3 bucket: {s3_bucket}')

        if datetime.now().hour == daily_backup_hour:
            if datetime.now().day == monthly_backup_day:
                backup_type = "monthly"
            else:
                backup_type = "daily"
        else:
            backup_type = "hourly"

        process = await asyncio.create_subprocess_shell(
            f"aws s3 sync server/1.19.1/backup/ s3://{s3_bucket}/{backup_type}/",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            limit=1024 * 512
        )

        try:
            while True:
                line = await process.stdout.readline()
                line = line.decode().rstrip()
                if line == '':
                    log('backup', 'got EOL - aborting s3 upload')
                    break
                elif f'upload: {path_to_backup}/{world_name} {file_date}.zip' in line:
                    log('backup', 's3 upload successful!')
                    os.remove(f"{path_to_backup}/{world_name} {file_date}.zip")
                    break
        except asyncio.LimitOverrunError:
            print("AsyncioLimitOverrunError - Separator not found, and Chunk limit is exceeded!\n"
                  "s3 upload aborted")

    async def bds_stdout_processor(self) -> AsyncIterable[str]:
        """Processes the raw BDS output before passing it"""
        while True:
            line = (await self.server.stdout.readline()).decode().rstrip()

            if f'{self.server_properties["level-name"]}/db/' in line:
                await self.initiate_backup(line.split(', '))

            elif 'Player connected: ' in line:
                gamertag = line[line.index(': ') + 2: line.index(',')]
                await self.player_event(gamertag, 'connect')
                yield line

            elif 'Player disconnected: ' in line:
                gamertag = line[line.index(': ') + 2: line.index(',')]
                await self.player_event(gamertag, 'disconnect')
                yield line

            elif "Version: " in line:
                self.version = line.split("Version: ")[1]
                self.config['last_saved_version'] = self.version
                json.dump(self.config, open('bdsconfig.json', "w"), indent=4)
                yield line

            elif "Quit correctly" in line:
                yield line
                raise errors.UserRequestedStop()

            elif line in ["Killed", "Crash"]:
                yield line
                raise errors.ServerCrash()

            elif line == "":
                pass

            else:
                yield line

    async def console_output(self):
        async for line in aiter(self.bds_stdout_processor()):
            log('server', line)

