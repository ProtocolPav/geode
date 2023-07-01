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
        self.previous_system_log = {'time': f"{datetime.now()}",
                                    'ram_used': 0,
                                    'ram_total': 0,
                                    'ram_percentage': 0,
                                    'cpu_percent': 0}
        self.config = json.load(open('bdsconfig.json', 'r'))
        self.server_count = 0
        self.hibernation_restart_valid = False

        print(self.config['title'])
        log("core", f"NexusCore Version: {self.version}")
        log("core", "Starting up NexusCore...")

    def server_running(self) -> bool:
        try:
            return self.server.running()
        except AttributeError:
            return False

    def server_status_check(self) -> bool:
        try:
            return self.server.status_check()
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

    async def smart_restart(self, threshold: int, trigger_value: int, max_threshold: int,
                            wait_before_enable: int):
        log('restart handler', f"Handler is set to smart mode. Trigger Value: {trigger_value}, "
                               f"Threshold: {threshold}%, Maximum Threshold: {max_threshold}%")

        await asyncio.sleep(wait_before_enable)

        system_logs: list[dict] = deepcopy(self.system_logs)
        system_logs.reverse()
        previous_log = system_logs[12]['ram_percentage']

        while self.server_status_check():
            system_logs: list[dict] = deepcopy(self.system_logs)
            system_logs.reverse()

            increase = system_logs[0]['ram_percentage'] - previous_log

            if increase >= trigger_value and system_logs[0]['ram_percentage'] >= threshold:
                log('restart handler', f'Handler has been triggered by the increase of {increase}! '
                                       f'(Trigger Value: {trigger_value})')
                await asyncio.sleep(1200)
                self.server.set_status("system_clearance")

            elif system_logs[0]['ram_percentage'] >= max_threshold:
                log('restart handler', f"Handler has been triggered by the threshold {system_logs[0]['ram_percentage']}! "
                                       f'(>={max_threshold}%)')
                self.server.set_status("system_clearance")

            previous_log = system_logs[0]['ram_percentage']
            self.previous_system_log = system_logs[0]

            await asyncio.sleep(60)

        log('restart handler', 'Exiting Smart Restart')
        raise errors.ServerStopped

    async def hibernation_restart(self, wait_before_enable: int):
        log('restart handler', 'Handler will restart the server if nobody has been online for 20 minutes')
        trigger = False

        await asyncio.sleep(wait_before_enable)

        while self.server_status_check():
            if self.server.online != 0:
                self.hibernation_restart_valid = True
                trigger = False

            elif self.server.online == 0 and not trigger and self.hibernation_restart_valid:
                log('restart handler', 'Server is empty. Waiting for 20 minutes')
                trigger = True
                await asyncio.sleep(1200)

            elif self.server.online == 0 and trigger:
                log('restart handler', 'Server has been empty for 20 minutes. Hibernation Restart has been triggered')
                self.hibernation_restart_valid = False
                self.server.set_status('system_clearance')

            await asyncio.sleep(60)

        log('restart handler', 'Exiting Hibernation Restart')
        raise errors.ServerStopped

    async def restart_loop(self):
        while True:
            log("looper", "Starting NexusCore Restart Handler...")
            self.config = json.load(open('bdsconfig.json', 'r'))
            restart_config = self.config['regular_restart']

            if self.config['regular_restart']['mode'] == 'default' and self.server_running():
                interval = restart_config['interval'] if restart_config['interval'] > 0 else 12000

                log('restart handler', 'Restart handler is set to default mode.')
                log('restart handler', f'Server will restart in {interval} seconds')
                await asyncio.sleep(interval)
                if self.server_running() and self.server_status_check():
                    self.server.set_status("system_clearance")
                else:
                    log('restart handler', f'Server is not in an appropriate state to restart. '
                                           f'(running:{self.server.running()}, status:{self.server.status[0]}, '
                                           f'status_check:{self.server_status_check()})')

            elif self.config['regular_restart']['mode'] == 'smart' and self.server_running():
                threshold = restart_config['threshold'] if restart_config['threshold'] > 50 else 70
                trigger_value = restart_config['trigger'] if restart_config['trigger'] > 3 else 4
                max_threshold = restart_config['max_threshold']
                wait_before_enable = restart_config['ignore_time'] if restart_config['ignore_time'] > 120 else 1200

                log('restart handler', 'Restart handler is set to smart mode.')
                log('restart handler', f'Handler will ignore logs for {wait_before_enable} seconds to ensure the server does not '
                                       f'enter a restart loop.')

                smart_restart_tasks = [asyncio.create_task(coro=self.smart_restart(threshold, trigger_value, max_threshold,
                                                                                   wait_before_enable),
                                                           name="Restart Handler Smart Restart"),
                                       asyncio.create_task(coro=self.hibernation_restart(wait_before_enable),
                                                           name="Restart Handler Hibernation Restart")]

                try:
                    await asyncio.gather(*smart_restart_tasks)

                except errors.ServerStopped:
                    log('restart handler', 'Handler canceling Smart Restart Tasks')
                    for restart_task in smart_restart_tasks:
                        log('restart handler', f'Canceling {restart_task.get_name()}')
                        restart_task.cancel()

            elif self.config['regular_restart']['mode'] not in ['smart', 'default']:
                log('restart handler', "Handler is not configured properly. Please set the mode to either 'default' or 'smart'.")
                await asyncio.sleep(1200)

            elif not self.server_running():
                log('restart handler', 'Waiting for server to go online...')
                await asyncio.sleep(30)

    async def responder_loop(self):
        log("looper", "Starting NexusCore Crash/Restart Responder...")

        while True:
            if self.server.status[0] == "server_crashed" and not self.server_running():
                log('nexus responder', 'Responding to server crash')
                self.server.set_status("responding_to_crash")

                system_logs: list[dict] = deepcopy(self.system_logs)
                system_logs.reverse()

                increase = system_logs[0]['ram_percentage'] - self.previous_system_log['ram_percentage']

                try:
                    log_index = system_logs.index(self.previous_system_log)
                except ValueError:
                    log_index = 12

                log('nexus responder', 'Sending last minute of logs:')

                for syslog in system_logs[0:log_index]:
                    log('nexus responder', f'{syslog}')

                log('nexus responder', f"Current Percent: {system_logs[0]['ram_percentage']}, "
                                       f"Previous Percent: {self.previous_system_log['ram_percentage']}, "
                                       f"Increase: {increase}")

                await asyncio.sleep(20)
                await self.start_server('started_by_system')

            elif self.server.status[0] == "system_clearance" and self.server_running():
                log('nexus responder', 'Regular server restart in progress...')
                await self.server.send_announce('The server will restart in §l§e60 seconds§r')
                await asyncio.sleep(30)
                await self.server.send_announce('The server will restart in §l§e30 seconds§r')
                await asyncio.sleep(25)
                await self.server.send_command('kick @a')
                await asyncio.sleep(5)

                await self.stop_server('executing_restart')

                await asyncio.sleep(20)
                await self.start_server('started_by_system')

            await asyncio.sleep(1)

    async def debug_loop(self):
        while True:
            try:
                for i in asyncio.all_tasks():
                    log('debug', f'Task: {i.get_name()}, {i.get_coro()}')

                await self.server.send_command('tell @a test message!')
            except AttributeError:
                await asyncio.sleep(10)
            finally:
                await asyncio.sleep(60)

    async def nexus_looper(self):
        log("core", "Starting NexusCore Looper...")
        system_logger = asyncio.create_task(coro=self.system_log_loop(),
                                            name='NexusCore Loop System Logger')
        restart_handler = asyncio.create_task(coro=self.restart_loop(),
                                              name='NexusCore Loop Restart Handler')
        responder = asyncio.create_task(coro=self.responder_loop(),
                                        name='NexusCore Loop Crash/Restart Responder')
        debug = asyncio.create_task(coro=self.debug_loop(),
                                    name='NexusCore Loop Debug Loop')
        await asyncio.gather(system_logger, restart_handler, responder, debug)
        log("core", "NexusCore Looper started successfully")

    async def start_server(self, start_status: str = 'started_by_user'):
        if not self.server_running():
            self.server_count += 1
            await self.server.disconnect_all()

            self.server = BedrockServer()

            try:
                asyncio.get_event_loop().create_task(coro=self.server.create_server(start_status),
                                                     name=f"Minecraft Server")

                if self.server_count == 1:
                    asyncio.get_event_loop().create_task(coro=self.nexus_looper(),
                                                         name=f"NexusCore Loop Handler")

            except errors.ServerStopped as e:
                if type(e) == errors.ServerCrash:
                    self.server.set_status('server_crashed')
                elif type(e) == errors.UserRequestedStop:
                    self.server.set_status('stopped_by_user')

    async def stop_server(self, stop_status: str = 'stopped_by_user'):
        if self.server.running():
            await self.server.disconnect_all()
            await self.server.send_command('stop')
            self.server.set_status(stop_status)


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
        self.status: list[str] = ['not_running']
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

    def status_check(self) -> bool:
        """
        Returns True only if the server status is in an acceptable state to perform actions
        """
        try:
            if self.status[0] in ['started_by_user', 'started_by_system']:
                return True

            return False
        except AttributeError:
            return False

    def set_status(self, new_status: str):
        log('server', f'Status updated from {self.status[0]} to {new_status}')
        self.status.insert(0, new_status)

    async def send_command(self, command: str, sleep: int = 0):
        self.server.stdin.write(f'{command}\n'.encode())
        await self.server.stdin.drain()
        await asyncio.sleep(sleep)

    async def send_message(self, message: str):
        await self.send_command(f"say {message}")

    async def send_announce(self, message: str):
        await self.send_command('execute at @a run playsound random.toast @a ~ ~3 ~ 100 0.2')
        await self.send_command(f'title @a actionbar {message}')

    async def check_for_updates(self):
        async with httpx.AsyncClient() as client:
            log('server', 'Checking for updates...')

            try:
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
            except httpx.TimeoutException:
                log('server', 'There was an issue with checking updates')

    async def backup_loop(self):
        log("server", "Starting Minecraft Server Backup Handler...")
        log('backup', 'Backups ENABLED' if self.config['backup']['enabled'] else 'Backups DISABLED')

        if self.config['backup']['enabled']:
            log('backup', 'Backups will happen every hour')
            await asyncio.sleep(80)
            while True:
                log('backup', "Beginning backup")
                if self.running() and self.status_check():
                    await self.send_command('save hold', sleep=5)
                    await self.send_command('save query', sleep=10)
                    await self.send_command('save resume', sleep=3580)
                else:
                    log('backup', f'Server is not in an acceptable state to backup. Aborting. '
                                  f'(running:{self.running()}, status:{self.status[0]}, '
                                  f'status_check:{self.status_check()})')
                    await asyncio.sleep(3600)

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
                                            name=f"[PID{self.process_id}] Minecraft Server Console Output"),
                        asyncio.create_task(coro=self.backup_loop(),
                                            name=f"[PID{self.process_id}] Minecraft Server Backup Loop")
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

        log("server", 'exiting console output')
