import asyncio
import json
import yaml
from typing import AsyncIterable
import shutil
import psutil
from datetime import datetime, timedelta
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


class LoopHandler:
    def __init__(self):
        self.loops = []
        self.tasks = []
        self.running = False

    def loop_task(self, task_name: str):
        def decorator(func):
            log("startup", f"Loading {task_name} ({func.__name__}) into the looper")
            self.loops.append({"function": func, "name": task_name})

        return decorator

    async def start_looper(self, nexuscore):
        log("core", "Starting NexusCore Looper...")
        self.tasks = []
        for i in self.loops:
            self.tasks.append(asyncio.create_task(coro=i["function"](nexuscore), name=i["name"]))

        self.running = True
        await asyncio.gather(*self.tasks)


class NexusCore:
    looper = LoopHandler()

    def __init__(self):
        self.version = 'v7.0'
        self.system_logs: list[dict] = []
        self.previous_system_log = {'time': f"{datetime.now()}",
                                    'ram_used': 0,
                                    'ram_total': 0,
                                    'ram_percentage': 0,
                                    'cpu_percent': 0}

        with open('nexusdata.json', 'r') as f:
            self.data = json.load(f)

        self.config = self.load_config_file()
        self.messages: list[dict] = []

        self.previous_backup = datetime.now().replace(year=1999)

        print(self.data['title'])
        log("core", f"NexusCore Version: {self.version}")
        log("core", "Starting up NexusCore...")
        self.server: BedrockServer = BedrockServer(self.config, self.data)

    @staticmethod
    def load_config_file() -> dict:
        with open('config.yml', 'r') as f:
            config: dict = yaml.safe_load(f)

            backup_config = config.get('backup', {})
            backup_config['enabled'] = backup_config.get('enabled', False)
            backup_config['cloud_platform'] = backup_config.get('cloud_platform', 's3')
            backup_config['cloud_bucket'] = backup_config.get('cloud_bucket', '')
            backup_config['interval'] = backup_config.get('interval', 3600)
            backup_config['startup_backup_enabled'] = backup_config.get('startup_backup_enabled', True)
            backup_config['daily_backup_hour'] = backup_config.get('daily_backup_hour', 18)
            backup_config['monthly_backup_day'] = backup_config.get('monthly_backup_day', 28)

            restart_config = config.get('restart_handler', {})
            restart_config['mode'] = restart_config.get('mode', 'default')
            restart_config['interval'] = restart_config.get('interval', 150000)
            restart_config['threshold'] = restart_config.get('threshold', 60)
            restart_config['max_threshold'] = restart_config.get('max_threshold', 85)
            restart_config['trigger'] = restart_config.get('trigger', 6)
            restart_config['ignore_time'] = restart_config.get('ignore_time', 1200)
            restart_config['empty_time'] = restart_config.get('empty_time', 1200)

            discord_config = config.get('discord_guild_id', 0)

            return {'backup': backup_config, 'restart_handler': restart_config, 'discord_guild_id': discord_config}

    def backup_check(self, startup: bool = False) -> bool:
        backup_interval = self.config['backup']['interval']
        if not startup and datetime.now() - self.previous_backup >= timedelta(seconds=backup_interval):
            return True
        elif startup and datetime.now() - self.previous_backup >= timedelta(seconds=backup_interval//2):
            return True
        else:
            return False

    @looper.loop_task("System Logger")
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
                                         'cpu_percent': cpu_usage,
                                         'online_players': len(self.server.online)})

                if len(self.system_logs) > 140000:
                    log('looper', 'Truncating system logs to 120000')
                    copy_logs = deepcopy(self.system_logs)
                    copy_logs.reverse()
                    copy_logs = copy_logs[0:120000]
                    copy_logs.reverse()
                    self.system_logs = copy_logs

                usage_file.seek(0)
                json.dump(self.system_logs, usage_file, indent=4)
                usage_file.truncate()

                await asyncio.sleep(10)

    @looper.loop_task("Restart Handler")
    async def restart_loop(self):
        while True:
            log("looper", "Starting NexusCore Restart Handler...")
            restart_config = self.config['restart_handler']

            if restart_config['mode'] == 'default' and self.server.running():
                interval = restart_config['interval']

                log('restart handler', 'Restart handler is set to default mode.')
                log('restart handler', f'Server will restart in {interval} seconds')
                await asyncio.sleep(interval)
                if self.server.running() and self.server.status_check():
                    self.server.set_status("system_clearance")
                else:
                    log('restart handler', f'Server is not in an appropriate state to restart. '
                                           f'(running:{self.server.running()}, status:{self.server.status[0]}, '
                                           f'status_check:{self.server.status_check()})')

            elif restart_config['mode'] != 'default' and self.server.running():
                log('restart handler', 'Restart handler is disabled. Checking again in 6 hours.')
                log('end of support', 'From v7.0 onwards, Smart restart mode is no longer supported.')
                await asyncio.sleep(21600)

            elif not self.server.running():
                log('restart handler', 'Waiting for server to go online...')
                await asyncio.sleep(30)

            await asyncio.sleep(60)

    @looper.loop_task("Crash Responder")
    async def responder_loop(self):
        log("looper", "Starting NexusCore Status Responder...")

        while True:
            if self.server.status[0] == "server_crashed" and not self.server.running():
                log('nexus responder', 'Responding to server crash...')
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

            elif self.server.status[0] == "system_clearance" and self.server.running():
                log('nexus responder', 'Regular server restart in progress...')
                await self.server.send_announce('The server will restart in §l§e60 seconds§r')
                await self.server.send_message('§e[Server Restart]§r All players will be §4kicked§r before server restart. '
                                               'You do not have to leave and §5will not lose any progress.§r')
                await self.server.send_message('§e[Server Restart]§r The server should be back in a few minutes. '
                                               'Remember to use /online to check the status of the server.')
                await asyncio.sleep(30)
                await self.server.send_announce('The server will restart in §l§e30 seconds§r')
                await asyncio.sleep(25)
                await self.server.send_announce('All players will now be kicked')
                for i in self.server.online:
                    await self.server.send_command(f'kick "{i}" Server Restart In Progress...')
                    await asyncio.sleep(0.5)
                await asyncio.sleep(3)

                await self.stop_server('executing_restart')

                await asyncio.sleep(20)
                await self.start_server('started_by_system')

            elif self.server.status[0] == "preemption":
                log('nexus responder', 'Preemption response in progress...')
                await self.server.send_announce('The server will restart in §l§e5 seconds§r')
                await self.server.send_message('§e[Server Restart]§r All players will be §4kicked§r before server restart. '
                                               'You do not have to leave and §5will not lose any progress.§r')
                await self.server.send_message('§e[Server Restart]§r NexusCore is expecting a server crash and is shutting down '
                                               'to avoid world corruption.')
                await self.server.send_message('§e[Server Restart]§r Thorny will be down as well during this time. Use '
                                               '/ping to check status')
                await asyncio.sleep(3)
                await self.server.send_announce('All players will now be kicked')
                await asyncio.sleep(1)
                for i in self.server.online:
                    await self.server.send_command(f'kick "{i}" §eNexusCore§r Status Responder successfully avoided a crash.')
                await asyncio.sleep(0.5)

                await self.stop_server('preemption_complete')

            await asyncio.sleep(1)

    @looper.loop_task("Backup Handler")
    async def backup_loop(self):
        log("looper", "Starting NexusLooper Backup Handler...")

        while True:
            if self.config['backup']['enabled']:
                log("looper", "Backups are enabled.")

                backup_interval = self.config['backup']['interval']
                log('backup', f'Backups will happen every {backup_interval//60} minutes')
                while self.server.running() and self.server.status_check() and self.backup_check():
                    log('backup', "Beginning backup")
                    self.previous_backup = datetime.now()
                    await self.server.send_command('save hold', sleep=5)
                    await self.server.send_command('save query', sleep=10)
                    await self.server.send_command('save resume', sleep=backup_interval - 15)
                else:
                    log('backup', f'Server is not in an acceptable state to backup. Aborting. '
                                  f'(running:{self.server.running()}, status:{self.server.status[0]}, '
                                  f'status_check:{self.server.status_check()}, backup_check:{self.backup_check()})')
                    if not self.backup_check():
                        extra_seconds = datetime.now() - self.previous_backup
                        await asyncio.sleep(backup_interval - extra_seconds.total_seconds())
                    else:
                        await asyncio.sleep(backup_interval)
            else:
                await asyncio.sleep(1600)

    @looper.loop_task("Config Reloader Loop")
    async def config_reloader(self):
        log('looper', 'Starting up Config Reloader')
        while True:
            log('core', 'Updating config file')
            self.config = self.load_config_file()
            log('debug', f'{self.config}')
            await asyncio.sleep(1200)

    @looper.loop_task("Message Scheduler Loop")
    async def message_scheduler(self):
        log('looper', 'Starting Message Scheduler')
        while True:
            try:
                message = self.messages[0]
                if message['time'] <= datetime.now().replace(microsecond=0, second=0):
                    self.messages.remove(message)
                    log('message scheduler', f'Sending message. There are now {len(self.messages)} remaining.')
                    if message['type'] == 'announce':
                        await self.server.send_announce(message['content'])
                    else:
                        await self.server.send_message(f"§e+=+=+=+=+=+=+ Server Message +=+=+=+=+=+=+§r\n{message['content']}")
            except IndexError:
                pass

            await asyncio.sleep(30)

    async def debug_loop(self):
        while True:
            try:
                for i in asyncio.all_tasks():
                    log('debug', f'Task: {i.get_name()}, {i.get_coro()}')

                await self.server.send_command('tell @r [DEBUG] Debug Message')
            except AttributeError:
                await asyncio.sleep(10)
            finally:
                await asyncio.sleep(60)

    async def startup_backup(self):
        backup_complete = False
        while not backup_complete:
            if self.server.running() and self.server.status_check() and self.backup_check(startup=True):
                log('core', 'Launching startup backup')
                self.previous_backup = datetime.now()
                await self.server.send_command('save hold', sleep=5)
                await self.server.send_command('save query', sleep=10)
                await self.server.send_command('save resume')
                backup_complete = True
            elif not self.backup_check():
                backup_interval = self.config['backup']['interval']
                log('core', f'Startup backup aborted. There was already a backup less than {backup_interval//2//60}m ago')
                break
            else:
                await asyncio.sleep(10)

        log('core', 'Startup backup complete')

    # noinspection PyAsyncCall
    async def start_server(self, start_status: str = 'started_by_user'):
        if not self.server.running():
            await self.server.disconnect_all()

            self.server = BedrockServer(self.config, self.data)

            try:
                asyncio.get_event_loop().create_task(coro=self.server.create_server(start_status),
                                                     name=f"Minecraft Server")

                if self.config['backup']['startup_backup_enabled'] and self.config['backup']['enabled']:
                    asyncio.get_event_loop().create_task(coro=self.startup_backup(),
                                                         name=f"Minecraft Server Startup Backup")

                if not NexusCore.looper.running:
                    asyncio.get_event_loop().create_task(coro=NexusCore.looper.start_looper(self),
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

    def __init__(self, config: dict, nexus_data: dict):
        self.start: datetime = datetime.now().replace(microsecond=0)
        self.status: list[str] = ['not_running']
        self.config = config
        self.data = nexus_data
        self.version: str = self.data['last_loaded_version']
        self.update = None
        self.discord_guild_id: int = self.config['discord_guild_id']
        self.process_id: int = 0
        self.online: list = []
        self.console_logs = []

        log('server', f'Last loaded version: {self.version}')

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
        log('command', f'Sending {command}')
        self.server.stdin.write(f'{command}\n'.encode())
        await self.server.stdin.drain()
        await asyncio.sleep(sleep)

    async def send_message(self, message: str):
        await self.send_command(f'tellraw @a {{"rawtext": [{{"text": "{message}"}}]}}')

    async def send_announce(self, message: str):
        await self.send_command('execute at @a run playsound random.toast @p ~ ~3 ~ 100 0.2')
        await self.send_command(f'title @a actionbar {message}')

    async def send_test_for(self, selectors: str):
        await self.send_command(f'testfor @a[{selectors}]')

    async def check_for_updates(self):
        async with httpx.AsyncClient() as client:
            log('server', 'Checking for updates...')

            try:
                server_download_site = await client.get("https://www.minecraft.net/en-us/download/server/bedrock",
                                                        follow_redirects=True,
                                                        headers={"Accept-Encoding": "identity", "Accept-Language": "en",
                                                                 "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

                soup = BeautifulSoup(server_download_site.text, 'html.parser')
                link = str(soup.find("a",
                                     href=re.compile("https://minecraft.azureedge.net/bin-linux/bedrock-server")).get('href'))

                if self.version not in link:
                    proc = await asyncio.create_subprocess_shell(
                        f"curl -H 'Cache-Control: no-cache, no-store' {link} --output server/temp.zip && "
                        f"unzip -o server/temp.zip -d server/new_server && "
                        f"cp -r server/1.19.1/worlds server/new_server/ &&"
                        f"cp server/1.19.1/allowlist.json server/new_server/ &&"
                        f"cp server/1.19.1/server.properties server/new_server/ &&"
                        f"cp server/1.19.1/permissions.json server/new_server/ &&"
                        f"cp -r server/1.19.1/config server/new_server/ &&"
                        f"cp -a server/1.19.1/. server/1.19.1-old/ &&"
                        f"rm -r server/1.19.1/* &&"
                        f"cp -a server/new_server/. server/1.19.1/",
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                    )
                    while True:
                        line = await proc.stdout.readline()
                        line = line.decode().rstrip()
                        if line == '':
                            log('debug', f'Aborting  due to EOL')
                            break
                        log('debug', f'{line}')

                    log('server', f"Server updated according to the link: {link}")

                    self.update = link.split('-')[3].split('.zip')[0]

                elif self.version in link:
                    self.update = None

                log('server', 'Server is up to date!')
            except httpx.TimeoutException:
                log('server', 'There was an issue with checking updates')

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

    async def disconnect_all(self):
        self.online = []

        async with httpx.AsyncClient() as client:
            sent_successfully = False
            while not sent_successfully:
                try:
                    await client.post(f"http://thorny-wbs:8000/disconnect/all?guild_id={self.discord_guild_id}")
                    sent_successfully = True

                except httpx.TimeoutException:
                    log('server', f"TimeoutException raised while sending 'disconnect all' event. Retrying in 30 seconds.")
                    await asyncio.sleep(30)

    async def initiate_backup(self, file_list: list[str]):
        path_to_worlds = 'server/1.19.1/worlds'
        path_to_backup = 'server/1.19.1/backup'
        daily_backup_hour = self.config['backup']['daily_backup_hour']
        monthly_backup_day = self.config['backup']['monthly_backup_day']
        world_name = self.server_properties['level-name']
        cloud_service = self.config['backup']['cloud_platform']
        bucket = self.config['backup']['cloud_bucket']

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
        log('backup', f'Beginning upload to {cloud_service} bucket: {bucket}')

        if datetime.now().hour == daily_backup_hour:
            if datetime.now().day == monthly_backup_day:
                backup_type = "monthly"
            else:
                backup_type = "daily"
        else:
            backup_type = "hourly"

        if cloud_service == 's3':
            process = await asyncio.create_subprocess_shell(
                f"aws s3 sync server/1.19.1/backup/ s3://{bucket}/{backup_type}/",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                limit=1024 * 512
            )

        else:
            process = await asyncio.create_subprocess_shell(
                f"./google-cloud-sdk/bin/gcloud config set storage/parallel_composite_upload_enabled False "
                f"&& ./google-cloud-sdk/bin/gcloud storage cp server/1.19.1/backup/*.zip gs://{bucket}/{backup_type}",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                limit=1024 * 512
            )

        try:
            while True:
                line = await process.stdout.readline()
                line = line.decode().rstrip()
                if line == '' and cloud_service == 's3':
                    log('backup', f'Aborting {cloud_service} upload due to EOL')
                    break
                elif cloud_service == 's3' and f'upload: {path_to_backup}/{world_name} {file_date}.zip' in line:
                    log('backup', 's3 upload successful!')
                    os.remove(f"{path_to_backup}/{world_name} {file_date}.zip")
                    break
                elif cloud_service == 'gcloud' and f'Average throughput:' in line:
                    log('backup', 'gcloud upload successful!')
                    os.remove(f"{path_to_backup}/{world_name} {file_date}.zip")
                    break
        except asyncio.LimitOverrunError:
            print("AsyncioLimitOverrunError - Separator not found, and Chunk limit is exceeded!\n"
                  f"{cloud_service} upload aborted")

    async def restore_backup(self, backup_type: str, file_name: str):
        cloud_service = self.config['backup']['cloud_platform']
        bucket = self.config['backup']['cloud_bucket']

        if cloud_service == 'gcloud':
            default_path = f'server/1.19.1/worlds/{self.server_properties["level-name"]}'
            restoration_path = f'server/1.19.1/worlds/{file_name}'

            process = await asyncio.create_subprocess_shell(
                f"./google-cloud-sdk/bin/gcloud config set storage/parallel_composite_upload_enabled False "
                f"&& ./google-cloud-sdk/bin/gcloud storage cp gs://{bucket}/{backup_type}/{file_name} server/1.19.1/worlds",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                limit=1024 * 512
            )

            try:
                while True:
                    line = await process.stdout.readline()
                    line = line.decode().rstrip()
                    log('restore backup', line)
                    if cloud_service == 'gcloud' and f'Average throughput:' in line:
                        log('backup', 'gcloud download successful!')
                        os.remove(f'{default_path}/level.dat')
                        os.remove(f'{default_path}/level.dat_old')
                        os.remove(f'{default_path}/db/*')

                        shutil.unpack_archive(restoration_path, f'{default_path}/')
                        break
            except asyncio.LimitOverrunError:
                print("AsyncioLimitOverrunError - Separator not found, and Chunk limit is exceeded!\n"
                      f"{cloud_service} upload aborted")
        else:
            log('restore backup', 'Restore backup only supported for gcloud buckets')

    async def bds_stdout_processor(self) -> AsyncIterable[str]:
        """
        Checks BDS output for any lines which require action to be taken
        """
        while True:
            line = (await self.server.stdout.readline()).decode().rstrip()

            if f'{self.server_properties["level-name"]}/db/' in line and 'Opening' not in line:
                await self.initiate_backup(line.split(', '))

            elif "Version" in line:
                self.version = line.split('Version')[-1].partition(' ')[-1]
                self.data['last_loaded_version'] = self.version
                with open('nexusdata.json', "w") as f:
                    f.seek(0)
                    json.dump(self.data, f, indent=4)
                    f.truncate()
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

            if "Scripting" in line:
                contents = [line]
            else:
                contents = line.split('] ')

            if len(contents) > 1 :
                console_log = contents[-1]
            else:
                console_log = line

            log('console', console_log)
            self.console_logs.append(console_log)

            if len(self.console_logs) >= 100:
                self.console_logs = self.console_logs[len(self.console_logs) - 50: len(self.console_logs)]

        log("server", 'exiting console output')
