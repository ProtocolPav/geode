import asyncio.subprocess
import asyncio
import platform
import re
from dataclasses import dataclass

from jproperties import Properties
from typing_extensions import Literal, Optional

from src import installation
from pathlib import Path

from sanic.log import logger, Colors

from src.handlers.backups import BackupHandler

from pyventus.events import EventLinker, AsyncIOEventEmitter

@dataclass
class EventParser:
    name: str
    regex: re.Pattern
    check_type: Literal['match', 'findall'] = 'match'


class BedrockServer:
    __process: asyncio.subprocess.Process | None
    __tasks: list[asyncio.Task]
    __event_emitter = AsyncIOEventEmitter()
    events: EventLinker = EventLinker
    status: Literal['stopped', 'started', 'backup', 'map_update'] = 'stopped'
    executable: str
    properties: dict[str, str]

    def __init__(self):
        if platform.system().lower() == 'linux':
            self.executable = './bedrock_server'
        else:
            raise OSError('Geode only supports Debian-based Linux distributions, we advise you to run Geode via Docker.')

        self.__process = None

        self.parsers = [
            # Player Events
            EventParser('player.connect', re.compile(r'Player connected: (.*), xuid: ([1-9]+)', re.IGNORECASE)),
            EventParser('player.spawn', re.compile(r'Player Spawned: (.*?)\s+xuid: (\d+)(?:, pfid: ([a-z0-9]+))?', re.IGNORECASE)),
            EventParser('player.disconnect', re.compile(r'Player disconnected: (.*), xuid: ([1-9]+)(?:, pfid: ([a-z0-9]+))?', re.IGNORECASE)),

            # Server Events
            EventParser('server.start', re.compile(r'^Server started', re.IGNORECASE)),
            EventParser('server.stop', re.compile(r'^Quit correctly', re.IGNORECASE)),
            EventParser('server.stop', re.compile(r'^Exiting program', re.IGNORECASE)),
            EventParser('server.crash', re.compile(r'^Killed', re.IGNORECASE)),
            EventParser('server.crash', re.compile(r'^Crash', re.IGNORECASE)),
            EventParser('server.version', re.compile(r'^Version:?\s*(\d+\.\d+\.\d+\.\d+)$', re.IGNORECASE)),

            # Backup Events
            EventParser('backup.hold', re.compile(r'Saving', re.IGNORECASE)),
            EventParser('backup.hold.error', re.compile(r'The command is already running', re.IGNORECASE)),
            EventParser('backup.query', re.compile(r'(?:^|,\s*)([^:]+):(\d+)(?=\s*(?:,|$))', re.IGNORECASE), 'findall'),
            EventParser('backup.error', re.compile(r'A previous save has not been completed', re.IGNORECASE)),
            EventParser('backup.resume', re.compile(r'Changes to the world are resumed', re.IGNORECASE)),
        ]

    async def send_command(self, command: str, sleep: int = 0):
        """
        Send a Minecraft command to the server.

        :param command: The command to send
        :param sleep: (Optional) The number of seconds to sleep after the command is sent
        """
        logger.debug(f'{Colors.GREY}Running Command {Colors.BLUE}{command}{Colors.END}')
        self.__process.stdin.write(f'{command}\n'.encode())
        await self.__process.stdin.drain()
        await asyncio.sleep(sleep)

    async def __server_output(self):
        """
        Processes the Minecraft BDS output and fires any events
        """
        while True:
            line = (await self.__process.stdout.readline()).decode().rstrip()
            line = '] '.join(line.split('] ')[1:]) if line.split('] ')[1:] else line

            parsed_line = False

            # This is a bit slow, should try reduce from O(n) to O(1)
            for event in self.parsers:
                if event.check_type == 'findall':
                    matches = event.regex.findall(line)
                    if matches:
                        parsed_line = True
                        self.emit(event.name, line, *matches)
                        break

                elif match := event.regex.search(line):
                    parsed_line = True
                    self.emit(event.name, line, *match.groups())
                    break

            if not parsed_line and line: # Check that a line exists so it wont print empty lines
                logger.info(line)
            elif parsed_line:
                logger.info(f'{Colors.YELLOW}{line}{Colors.END}')

    async def start(self):
        if not self.__process or self.__process.returncode is not None:
            await installation.check_for_updates()

            prop_file = Properties()
            prop_file.load(open('../server/server.properties', 'rb'))
            self.properties = prop_file.properties
            logger.debug(f'Loaded properties: {self.properties}')

            self.__process = await asyncio.subprocess.create_subprocess_exec(
                program=self.executable,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit= 1024 * 512,
                cwd='../server/')
            logger.debug(f'Created BedrockServer process PID{self.__process.pid}')

            self.__tasks = [
                asyncio.create_task(self.__server_output(), name=f"[{self.__process.pid}] BDS Output")
            ]

            await asyncio.gather(*self.__tasks)

            logger.debug(f'Current tasks: {self.__tasks}')

    async def stop(self):
        if self.__process:
            await self.send_command('stop')

    def emit(self, event_name: str, *args, **kwargs):
        self.__event_emitter.emit(event_name, self, *args, **kwargs)

    @events.on('server.start')
    async def on_server_start(self, line: str):
        """
        When the server has started and is ready for playing.

        :param line: The console log line where the event occurs
        """
        self.status = 'started'
        # TO ADD: Disconnect all connected players, in case there was a glitch
        # Log to all the correct locations

    @events.on('server.stop')
    async def on_server_stop(self, line: str):
        """
        When the server has stopped.

        :param line: The console log line where the event occurs
        """
        self.status = 'stopped'

        for task in self.__tasks:
            task.cancel()

        self.__process.terminate()
        # Clean up pending tasks, like the server output, etc.
        # TO ADD: Disconnect all connected players
        # Log to all the correct locations

    @events.on('server.version')
    async def on_server_version(self, line: str, version: str):
        """
        When the server version is detected by the console.

        :param line: The console log line where the event occurs
        :param version: The version found
        """
        version_file = Path('../server/version.geode')
        version_file.write_text(version)

    @events.on('player.connect')
    async def on_player_connect(self, line: str, gamertag: str, xuid: Optional[str]):
        """
        When a player connects to the server. This doesn't mean the player has spawned in the world.

        :param line: The console log line where the event occurs
        :param gamertag: The gamertag of the connected player
        :param xuid: The xuid of the connected player. Can be None.
        """
        ...

    @events.on('player.spawn')
    async def on_player_spawn(self, line: str, gamertag: str, xuid: Optional[str], pfid: Optional[str]):
        """
        When a player spawns in the world, after they have connected.

        :param line: The console log line where the event occurs
        :param gamertag: The gamertag of the player
        :param xuid: The xuid of the player. Can be None.
        :param pfid: The pfid of the player. Can be None.
        """
        ...

    @events.on('player.disconnect')
    async def on_player_disconnect(self, line: str, gamertag: str, xuid: Optional[str], pfid: Optional[str]):
        """
        When a player disconnects from the server.

        :param line: The console log line where the event occurs
        :param gamertag: The gamertag of the player
        :param xuid: The xuid of the player. Can be None.
        :param pfid: The pfid of the player. Can be None.
        """
        ...

    @events.on('backup.hold')
    async def on_backup_hold(self, line: str):
        await self.send_command('save query')

    @events.on('backup.query')
    async def on_backup_query(self, line: str, *file_list: tuple):
        backup_handler = BackupHandler(file_list, self.properties['level-name'])

        if self.status == 'map_update':
            await backup_handler.map_update()
        elif self.status == 'backup':
            await backup_handler.backup()

        await self.send_command('save resume')

    @events.on('backup.error')
    async def on_backup_error(self, line: str):
        await self.send_command('save query')

    @events.on('backup.resume')
    async def on_backup_resume(self, line: str):
        self.status = 'started'

    @events.on('initiate.backup')
    async def on_initiate_backup(self):
        if self.status == 'started':
            await self.send_command('save hold')
            self.status = 'backup'
        else:
            logger.warn('Cannot initiate backup because the server is not running.')

    @events.on('initiate.map.render')
    async def on_initiate_backup(self):
        if self.status == 'started':
            await self.send_command('save hold')
            self.status = 'map_update'
        else:
            logger.warn('Cannot initiate map update because the server is not running.')

    @events.on('preemption')
    async def on_preemption(self):
        # Handle Preemption
        await self.stop()
