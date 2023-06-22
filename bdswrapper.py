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

class ServerStop(Exception):
    def __init__(self, requested_by_user: bool):
        super().__init__()

        self.user_stop = requested_by_user


async def initiate_backup(file_list, world_name: str, process_id: int, s3_bucket: str):
    path_to_worlds = 'server/1.19.1/worlds'
    path_to_backup = 'server/1.19.1/backup'
    daily_backup_hour = 16
    monthly_backup_day = 28

    file_date = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    os.makedirs(f'{path_to_backup}/{world_name} {file_date}/db')

    for file in file_list:
        file_path = file.split('/')
        file_to_copy = file_path[-1].split(':')[0]
        file_length = int(file_path[-1].split(':')[1])

        db = "db" if 'db' in file_path else ""

        original_path = f"{path_to_worlds}/{world_name}/{db}/{file_to_copy}"
        destination_path = f"{path_to_backup}/{world_name} {file_date}/{db}/{file_to_copy}"

        shutil.copyfile(original_path, destination_path)

        with open(destination_path, 'a') as f:
            f.truncate(file_length)

    shutil.make_archive(f"{path_to_backup}/{world_name} {file_date}", 'zip',
                        f"{path_to_backup}/{world_name} {file_date}")
    shutil.rmtree(f"{path_to_backup}/{world_name} {file_date}")

    size = os.path.getsize(f"{path_to_backup}/{world_name} {file_date}.zip")

    print(f"[PID{process_id}] [{datetime.now().replace(microsecond=0)} BACKUP] Finished backup")
    print(f"[PID{process_id}] [{datetime.now().replace(microsecond=0)} BACKUP] This backup is {round(size / 1000 / 1000, 2)}MB")
    print(f"[PID{process_id}] [{datetime.now().replace(microsecond=0)} BACKUP] Beginning s3 upload to {s3_bucket}...")

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
                print("got EOL - aborting s3 upload")
                break
            elif f'upload: {path_to_backup}/{world_name} {file_date}.zip' in line:
                print(f"[PID{process_id}] [{datetime.now().replace(microsecond=0)} BACKUP] s3 upload successful!")
                os.remove(f"{path_to_backup}/{world_name} {file_date}.zip")
                break
    except asyncio.LimitOverrunError:
        print("AsyncioLimitOverrunError - Separator not found, and Chunk limit is exceeded!\n"
              "s3 upload aborted")


class BedrockServer:
    client: asyncio.subprocess.Process
    start_time: datetime
    logs: list[str]
    system_logs: list[dict]
    status: str
    server_properties: dict
    config: dict
    version: str
    discord_guild_id: int
    process_id: int

    def __init__(self, handler):
        self.logs = []
        self.server_properties = {}
        self.config = json.load(open("bdsconfig.json", "r"))
        self.version = self.config['last_saved_version']
        self.discord_guild_id = self.config['discord_guild_link']
        self.handler = handler
        self.status = ""
        self.previous_system_log = {'time': f"{datetime.now()}",
                                    'ram_used': 0,
                                    'ram_total': 0,
                                    'ram_percentage': 0,
                                    'cpu_percent': 0}
        self.start_time = datetime.now().replace(microsecond=0)

        print(f'[SERVER] Last saved version loaded as {self.version}')

        prop_file = Properties()
        prop_file.load(open("server/1.19.1/server.properties", 'rb'))
        self.server_properties = prop_file.properties

    def client_running(self) -> bool:
        try:
            return True if self.client.returncode is None else False
        except AttributeError:
            return False

    def set_status(self, status: str):
        previous_status = self.status
        self.status = status

        print(f"[PID{self.process_id}] [SERVER] Server status updated from {previous_status} to {self.status}")

    async def execute(self, text: str, sleep=0):
        self.client.stdin.write(f'{text}\n'.encode())
        await self.client.stdin.drain()
        await asyncio.sleep(sleep)

    async def bds_stdout_processor(self) -> AsyncIterable[str]:
        """Processes the raw BDS output before passing it"""
        while True:
            line = (await self.client.stdout.readline()).decode().rstrip()

            if f'{self.server_properties["level-name"]}/db/' in line:
                await initiate_backup(line.split(', '),
                                      self.server_properties["level-name"],
                                      self.process_id,
                                      self.config['backup']['s3_bucket'])

            elif 'Player connected: ' in line:
                async with AsyncClient() as client:
                    gamertag = line[line.index(': ') + 2 : line.index(',')]
                    await client.post(f"http://thorny-wbs:8000/<guild_id:{self.discord_guild_id}>/<gamertag:{gamertag}>/connect")
                    yield line

            elif 'Player disconnected: ' in line:
                async with AsyncClient() as client:
                    gamertag = line[line.index(': ') + 2: line.index(',')]
                    await client.post(f"http://thorny-wbs:8000/<guild_id:{self.discord_guild_id}>/<gamertag:{gamertag}>/disconnect")
                    yield line

            elif "Version: " in line:
                self.version = line.split("Version: ")[1]
                self.config['last_saved_version'] = self.version
                json.dump(self.config, open('bdsconfig.json', "w"), indent=4)
                yield line

            elif "Quit correctly" in line:
                yield line
                raise ServerStop(requested_by_user=True)

            elif line == "Killed":
                yield line
                raise ServerStop(requested_by_user=False)

            else:
                yield line

            self.logs.append(line)

    async def console_output(self):
        async for line in aiter(self.bds_stdout_processor()):
            print(f"[PID{self.process_id}]", line)

    async def backup_loop(self):
        print('[SERVER]', 'Backups ENABLED' if self.config['backup']['enabled'] else 'Backups DISABLED')

        if self.config['backup']['enabled']:
            while True:
                await asyncio.sleep(50)
                print(f"[PID{self.process_id}] [{datetime.now().replace(microsecond=0)} BACKUP] Beginning backup")
                await self.execute('save hold', sleep=5)
                await self.execute('save query', sleep=10)
                await self.execute('save resume', sleep=3835)

    async def regular_restart(self):
        if self.config['regular_restart']['mode'] == 'smart':
            threshold = self.config['regular_restart']['threshold'] if self.config['regular_restart']['threshold'] > 50 else 60
            trigger_value = self.config['regular_restart']['trigger'] if self.config['regular_restart']['trigger'] > 1 else 4

            print(f"[PID{self.process_id}] [SERVER] Regular Restart is set to smart mode")
            await self.smart_restart(threshold, trigger_value)

        elif self.config['regular_restart']['mode'] == 'default':
            interval = self.config['regular_restart']['interval'] if self.config['regular_restart']['interval'] > 0 else 12000

            print(f"[PID{self.process_id}] [SERVER] Regular Restart is configured to restart every {interval} seconds")
            await asyncio.sleep(interval)
            self.set_status("system_clearance")

        else:
            print(f"[PID{self.process_id}] [SERVER] Regular Restart is not configured. "
                  f"Please choose either 'smart' or 'default' modes in the config file.")


    async def smart_restart(self, threshold: int, trigger_value: int):
        print(f"[PID{self.process_id}] [SERVER] Smart Restart is active. Trigger Value: {trigger_value}, "
              f"Threshold: {threshold}%, Maximum Threshold: 92%")
        system_logs: list[dict] = deepcopy(self.handler.system_logs)
        system_logs.reverse()
        previous_log = system_logs[12]['ram_percentage']
        while self.status != "system_clearance":
            system_logs: list[dict] = deepcopy(self.handler.system_logs)
            system_logs.reverse()

            increase = system_logs[0]['ram_percentage'] - previous_log

            # try:
            #     print(f"[PID{self.process_id}] [{datetime.now().replace(microsecond=0)} SERVER] "
            #           f"The index of the previous log is: {system_logs.index(self.previous_system_log)}")
            # except ValueError:
            #     pass
            #
            # print(f"[PID{self.process_id}] [{datetime.now().replace(microsecond=0)} SERVER] "
            #       f"Current Percent: {system_logs[0]['ram_percentage']}, Previous Percent: {previous_log}, Increase: {increase}")

            if increase >= trigger_value and system_logs[0]['ram_percentage'] >= threshold:
                print(f"[PID{self.process_id}] [{datetime.now().replace(microsecond=0)} SERVER] "
                      f"Smart Restart has been triggered by the increase of {increase}! (Trigger Value: {trigger_value})")
                await asyncio.sleep(1200)
                self.set_status("system_clearance")

            elif system_logs[0]['ram_percentage'] >= 92:
                print(f"[PID{self.process_id}] [{datetime.now().replace(microsecond=0)} SERVER] "
                      f"Smart Restart has found that {system_logs[0]['ram_percentage']} is very high")
                self.set_status("system_clearance")

            previous_log = system_logs[0]['ram_percentage']
            self.previous_system_log = system_logs[0]

            await asyncio.sleep(60)

    async def create_client(self):
        self.client = await asyncio.create_subprocess_shell("cd server/1.19.1 && LD_LIBRARY_PATH=. ./bedrock_server",
                                                            stdin=asyncio.subprocess.PIPE,
                                                            stdout=asyncio.subprocess.PIPE,
                                                            stderr=asyncio.subprocess.STDOUT,
                                                            limit= 1024 * 512
                                                            )

        self.process_id = self.client.pid

        server_tasks = [asyncio.create_task(coro=self.console_output(),
                                            name=f"[PID{self.process_id}] Minecraft Server Console Output"),
                        asyncio.create_task(coro=self.backup_loop(),
                                            name=f"[PID{self.process_id}] Minecraft Server Backup Handler"),
                        asyncio.create_task(coro=self.regular_restart(),
                                            name=f"[PID{self.process_id}] Minecraft Server Regular Restart")
                        ]

        for key, val in self.server_properties.items():
            print(f"[INFO] {key} = {val}")

        try:
            await asyncio.gather(*server_tasks)

        except ServerStop as e:
            if e.user_stop:
                self.set_status("stopped_by_user")
                print(f"[{datetime.now().replace(microsecond=0)} SERVER] Server stop requested by user")
            else:
                self.set_status("server_crashed")
                print(f"[{datetime.now().replace(microsecond=0)} SERVER] Server has crashed")

            print(f"[{datetime.now().replace(microsecond=0)} SERVER] Canceling all running tasks...")

            for task in server_tasks:
                print(f"[{datetime.now().replace(microsecond=0)} SERVER] Canceling task {task.get_name()}")
                task.cancel()


class Handler:
    handler_version: str = "v4.5"
    system_logs: list[dict] = []
    server: BedrockServer
    config: dict
    new_update: str

    def server_running(self) -> bool:
        try:
            return self.server.client_running()
        except AttributeError:
            return False

    async def check_for_crash(self):
        print('[HANDLER] Starting AutoRestart...')
        while True:
            if self.server.status == "server_crashed" and not self.server_running():
                print(f"[{datetime.now().replace(microsecond=0)} HANDLER] Responding to server crash...")
                self.server.set_status("responding_to_crash")

                system_logs: list[dict] = deepcopy(self.system_logs)
                system_logs.reverse()

                increase = system_logs[0]['ram_percentage'] - self.server.previous_system_log['ram_percentage']

                try:
                    log_index = system_logs.index(self.server.previous_system_log)
                except ValueError:
                    log_index = 12

                for log in system_logs[0:log_index]:
                    print(f"[{datetime.now().replace(microsecond=0)} Crash Responder] "
                          f"{log}")

                print(f"[{datetime.now().replace(microsecond=0)} Crash Responder] "
                      f"Current Percent: {system_logs[0]['ram_percentage']}, "
                      f"Previous Percent: {self.server.previous_system_log['ram_percentage']}, "
                      f"Increase: {increase}")

                await asyncio.sleep(20)
                await self.start_server()

            elif self.server.status == "system_clearance" and self.server_running():
                print(f"[{datetime.now().replace(microsecond=0)} HANDLER] Regular Server Restart...")
                await self.execute_message("The server will restart in 60 seconds. You can join back straight away!")
                await asyncio.sleep(60)

                await self.stop_server()
                self.server.set_status("executing_restart")

                await asyncio.sleep(20)
                await self.start_server()

            await asyncio.sleep(1)

    async def log_system_usage(self):
        print('[HANDLER] Starting SystemLogger...')
        with open("system_usage.json", "r+") as usage_file:
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

    async def start_server(self):
        self.config = json.load(open("bdsconfig.json", "r"))

        if not self.server_running():
            print(f'HANDLER VERSION {self.handler_version}')
            async with httpx.AsyncClient() as client:
                await client.post(f'http://thorny-wbs:8000/<guild_id:{self.config["discord_guild_link"]}>/disconnect/all')

            self.server = BedrockServer(self)
            await self.check_for_updates()
            await asyncio.sleep(10)

            asyncio.get_event_loop().create_task(coro=self.server.create_client(),
                                                 name=f"Minecraft Server")

    async def stop_server(self):
        if self.server_running():
            async with httpx.AsyncClient() as client:
                await client.post(f'http://thorny-wbs:8000/<guild_id:{self.config["discord_guild_link"]}>/disconnect/all')

            await self.server.execute('stop')

    async def check_for_updates(self):
        async with httpx.AsyncClient() as client:
            print("[HANDLER] Checking for updates...")
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

            if self.server.version not in link:
                await asyncio.create_subprocess_shell(
                    f"curl -H 'Cache-Control: no-cache, no-store' {link} --output server/temp.zip && "
                    f"unzip -o server/temp.zip bedrock_server -d server/temp && "
                    f"cp server/temp/bedrock_server server/1.19.1/bedrock_server",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                print(f"[HANDLER] I have updated the server according to the link {link}")

                self.new_update = link.split('-')[3].split('.zip')[0]

            elif self.server.version in link and hasattr(self, 'new_update'):
                self.__delattr__('new_update')

            print("[HANDLER] The server is up to date!")

    async def execute_backup(self):
        await self.server.execute('save hold', sleep=2)
        await self.server.execute('save query', sleep=10)
        await self.server.execute('save resume')

    async def execute_whitelist(self, gamertag: str, operation: str):
        if operation.lower() == "remove":
            await self.server.execute(f'allowlist remove "{gamertag}"')
        else:
            await self.server.execute(f'allowlist add "{gamertag}"')

    async def execute_kick(self, gamertag: str):
        await self.server.execute(f'kick "{gamertag}"')

    async def execute_message(self, message: str):
        await self.server.execute(f"say {message}")

    async def backups_list(self):
        backups = []
        process = await asyncio.create_subprocess_shell(
            f"aws s3 ls s3://everthorn-backups/hourly/",
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
                    print("got EOL - all backups retrieved")
                    break
                elif self.server.server_properties['level-name'] in line:
                    size = int(line.split("  ")[1].split(" ")[0]) / 1024 / 1024
                    name = line.split("  ")[1].split(" ")[1]
                    date = line.split("  ")[1].split(" ")[2]
                    time = line.split("  ")[1].split(" ")[3].strip(".zip")
                    backups.append({'world_name': name,
                                    'backup_size_MiB': size,
                                    'backup_date': datetime.fromisoformat(date),
                                    'backup_time': time})
        except asyncio.LimitOverrunError:
            print("AsyncioLimitOverrunError - Separator not found, and Chunk limit is exceeded!\n"
                  "s3 list aborted")