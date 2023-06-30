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
        self.server_count = 0

        print(self.config['title'])
        log("core", f"NexusCore Version: {self.version}")
        log("core", "Starting up NexusCore...")

    def server_running(self) -> bool:
        try:
            return self.server.running()
        except AttributeError:
            return False

    def server_status_check(self) -> bool:
        """
        Returns True only if the server status is in an acceptable state to perform actions
        """
        try:
            if self.server.status in ['started_by_user', 'started_by_system']:
                return True

            return False
        except AttributeError:
            return False

    async def system_log_loop(self):
        log("looper", "Starting NexusCore System Logger...")
        with open("./system_usage.json", "r+") as usage_file:
            self.system_logs = json.load(usage_file)
            while True:
                ram_usage = psutil.virtual_memory()
                cpu_usage = psutil.cpu_percent(None)
                self.system_logs.append({'time': f"{datetime.now()}",
                                         'ram_used': ram_usage.used,
                                         'ram_total': ram_usage.total,
                                         'ram_percentage': ram_usage.percent,
                                         'cpu_percent': cpu_usage})

                usage_file.seek(0)
                json.dump(self.system_logs, usage_file, indent=4)
                usage_file.truncate()

                await asyncio.sleep(10)

    async def backup_loop(self):
        log("looper", "Starting NexusCore Backup Handler...")
        log('backup', 'Backups ENABLED' if self.config['backup']['enabled'] else 'Backups DISABLED')

        if self.config['backup']['enabled']:
            log('backup', 'Backups will happen every hour')
            while True:
                log('backup', "Beginning backup")
                if self.server_running() and self.server_status_check():
                    await self.server.send_command('save hold', sleep=5)
                    await self.server.send_command('save query', sleep=10)
                    await self.server.send_command('save resume', sleep=3580)
                else:
                    log('backup', f'Server is not in an acceptable state to backup. Aborting. '
                                  f'(running:{self.server.running()}, status:{self.server.status}, '
                                  f'status_check:{self.server_status_check()})')
                    await asyncio.sleep(3600)

    async def restart_loop(self):
        log("looper", "Starting NexusCore Restart Handler...")

    async def crash_loop(self):
        log("looper", "Starting NexusCore Crash Handler...")

    async def nexus_looper(self):
        log("core", "Starting NexusCore Looper...")
        await asyncio.gather(asyncio.create_task(coro=self.system_log_loop(),
                                                 name='NexusCore Loop System Logger'),
                             asyncio.create_task(coro=self.backup_loop(),
                                                 name='NexusCore Loop Backup Handler'),
                             asyncio.create_task(coro=self.restart_loop(),
                                                 name='NexusCore Loop Restart Handler'),
                             asyncio.create_task(coro=self.crash_loop(),
                                                 name='NexusCore Loop Crash Handler')
                             )
        log("core", "NexusCore Looper started successfully")

    async def server_backup(self):
        backup_complete = False
        while not backup_complete:
            if self.server_running() and self.server_status_check():
                log('core', 'Launching startup backup')
                await self.server.send_command('save hold', sleep=5)
                await self.server.send_command('save query', sleep=10)
                await self.server.send_command('save resume')
                backup_complete = True
            else:
                await asyncio.sleep(10)

    async def start_server(self, start_status: str = 'started_by_user'):
        if self.server_count == 0:
            asyncio.get_event_loop().create_task(coro=self.nexus_looper(),
                                                 name=f"NexusCore Loop Handler")

        if not self.server_running():
            self.server_count += 1
            await self.server.disconnect_all()

            self.server = BedrockServer()

            try:
                asyncio.get_event_loop().create_task(coro=self.server.create_server(start_status),
                                                     name=f"Minecraft Server")
                asyncio.get_event_loop().create_task(coro=self.server_backup(),
                                                     name=f"Minecraft Server Startup Backup")

            except errors.ServerStopped as e:
                if type(e) == errors.ServerCrash:
                    self.server.set_status('server_crashed')
                elif type(e) == errors.UserRequestedStop:
                    self.server.set_status('stopped_by_user')

    async def stop_server(self):
        if self.server.running():
            await self.server.disconnect_all()
            await self.server.send_command('stop')



class BedrockServer:
    """
    All possible statuses:
    not_running: The server is not running. This is only set during class initialization
    started_by_user: The user requested to start the server
    started_by_system: The system has requested to start the server
    stopped_by_user: The user requested to stop the server
    stopped_by_system: The system has requested to stop the server
    system_clearance: The system is preparing for a server restart
    executing_restart: The system is currently executing the restart
    server_crashed: The server has crashed
    responding_to_crash: The system is responding to the crash, usually a restart
    """

    server: asyncio.subprocess.Process

    def __init__(self):
        self.start: datetime = datetime.now().replace(microsecond=0)
        self.status: str = 'not_running'
        self.config: dict = json.load(open("bdsconfig.json", "r"))
        self.version: str = self.config['last_saved_version']
        self.update = None
        self.discord_guild_id: int = self.config['discord_guild_link']
        self.process_id: int = 0
        self.online: int = 0

        log('server', f'Last saved version loaded as {self.version}')

        prop_file = Properties()
        prop_file.load(open("server/1.19.1/server.properties", 'rb'))
        self.server_properties = prop_file.properties

    def running(self) -> bool:
        try:
            return True if self.server.returncode is None else False
        except AttributeError:
            return False

    def set_status(self, new_status: str):
        log('server', f'Status updated from {self.status} to {new_status}')
        self.status = new_status

    async def send_command(self, command: str, sleep: int = 0):
        self.server.stdin.write(f'{command}\n'.encode())
        await self.server.stdin.drain()
        await asyncio.sleep(sleep)

    async def check_for_updates(self):
        async with httpx.AsyncClient() as client:
            log('server', 'Checking for updates...')

            server_download_site = await client.get("https://www.minecraft.net/en-us/download/server/bedrock",
                                                    follow_redirects=True,
                                                    headers={"Accept-Encoding": "identity", "Accept-Language": "en",
                                                             "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

            soup = BeautifulSoup(server_download_site.text, 'html.parser')
            link = str(soup.find("a", href=re.compile("https://minecraft.azureedge.net/bin-linux/bedrock-server")).get('href'))

            # New command testing.
            # curl -H 'Cache-Control: no-cache, no-store' {link} --output server/temp.zip
            # unzip server/temp.zip -d server/new_server
            # cp server/1.19.1/worlds server/new_server/ -r
            # cp server/1.19.1/allowlist.json server/new_server/
            # cp server/1.19.1/server.properties server/new_server/
            # cp server/1.19.1/permissions.json server/new_server/
            # I should run mv to rename 1.19.1 to 1.19.1-old and the new_server to 1.19.1
            # But this throws an error right now. Unsure why.

            if self.version not in link:
                await asyncio.create_subprocess_shell(
                    f"curl -H 'Cache-Control: no-cache, no-store' {link} --output server/temp.zip && "
                    f"unzip -o server/temp.zip bedrock_server -d server/temp && "
                    f"cp server/temp/bedrock_server server/1.19.1/bedrock_server",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                log('server', f"Server updated according to the link: {link}")

                self.update = link.split('-')[3].split('.zip')[0]

            elif self.version in link:
                self.update = None

            log('server', 'Server is up to date!')

    async def create_server(self, start_status: str = 'started_by_user'):
        await self.check_for_updates()

        log('server', 'Starting server...')
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
        if event == 'connect':
            self.online += 1
        else:
            self.online -= 1

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

    async def disconnect_all(self):
        async with httpx.AsyncClient() as client:
            sent_successfully = False
            while not sent_successfully:
                try:
                    await client.post(f"http://thorny-wbs:8000/"
                                      f"<guild_id:{self.config['discord_guild_link']}>/"
                                      f"disconnect/all")
                    sent_successfully = True

                except httpx.TimeoutException:
                    log('server', f"TimeoutException raised while sending 'disconnect all' event. Retrying in 30 seconds.")
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
            print(line)
