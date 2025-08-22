import asyncio.subprocess
import asyncio
import platform

from typing_extensions import Literal, Optional

from src import installation
from pathlib import Path

from sanic.log import logger, Colors

from src.handlers.events import EventHandler


class BedrockServer:
    __process: asyncio.subprocess.Process | None
    __tasks: asyncio.TaskGroup
    events: EventHandler = EventHandler()
    status: Literal['stopped', 'started', 'backup', 'map_update'] = 'stopped'

    def __init__(self):
        if platform.system().lower() == 'linux':
            self.executable = './bedrock_server'
        else:
            raise OSError('Geode only supports Debian-based Linux distributions, we advise you to run Geode via Docker.')

        self.__process = None

    async def send_command(self, command: str, sleep: int = 0):
        """
        Send a Minecraft command to the server.

        :param command: The command to send
        :param sleep: (Optional) The amount of seconds to sleep after the command is sent
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

            parsed_line = self.events.parse(line)

            if parsed_line is not None:
                await parsed_line.callback(self, line, *parsed_line.args)
            elif line:  # Won't print empty lines
                logger.info(line)

    async def start(self):
        if not self.__process:
            await installation.check_for_updates()

            self.__process = await asyncio.subprocess.create_subprocess_exec(
                program=self.executable,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit= 1024 * 512,
                cwd='../server/')
            logger.debug(f'Created BedrockServer process PID{self.__process.pid}')

            async with asyncio.TaskGroup() as self.__tasks:
                self.__tasks.create_task(self.__server_output(), name=f"[{self.__process.pid}] BDS Output")

            logger.debug(f'Current tasks: {self.__tasks}')

    async def stop(self):
        if self.__process:
            await self.send_command('stop')

    async def initiate_backup(self):
        if self.status == 'started':
            await self.send_command('save hold')
            self.status = 'backup'
        else:
            logger.warn('Cannot initiate backup because the server is not running.')

    async def initiate_map_update(self):
        if self.status == 'started':
            await self.send_command('save hold')
            self.status = 'map_update'
        else:
            logger.warn('Cannot initiate map update because the server is not running.')

    @events.listen('server.start')
    async def on_server_start(self, line: str):
        """
        When the server has started and is ready for playing.

        :param line: The console log line where the event occurs
        """
        logger.info(f'{Colors.YELLOW}{line}{Colors.END}')
        self.status = 'started'
        # TO ADD: Disconnect all connected players, in case there was a glitch
        # Log to all the correct locations

    @events.listen('server.stop')
    async def on_server_stop(self, line: str):
        """
        When the server has stopped.

        :param line: The console log line where the event occurs
        """
        logger.info(f'{Colors.YELLOW}{line}{Colors.END}')
        self.status = 'stopped'
        # Clean up pending tasks, like the server output, etc.
        # TO ADD: Disconnect all connected players
        # Log to all the correct locations

    @events.listen('server.version')
    async def on_server_version(self, line: str, version: str):
        """
        When the server version is detected by the console.

        :param line: The console log line where the event occurs
        :param version: The version found
        """
        logger.info(f'{Colors.BOLD}{Colors.PURPLE}{line}{Colors.END}')
        version_file = Path('../server/version.geode')
        version_file.write_text(version)

    @events.listen('player.connect')
    async def on_player_connect(self, line: str, gamertag: str, xuid: Optional[str]):
        """
        When a player connects to the server. This doesn't mean the player has spawned in the world.

        :param line: The console log line where the event occurs
        :param gamertag: The gamertag of the connected player
        :param xuid: The xuid of the connected player. Can be None.
        """
        logger.info(f'{Colors.YELLOW}{line}{Colors.END}')

    @events.listen('player.spawn')
    async def on_player_spawn(self, line: str, gamertag: str, xuid: Optional[str], pfid: Optional[str]):
        """
        When a player spawns in the world, after they have connected.

        :param line: The console log line where the event occurs
        :param gamertag: The gamertag of the player
        :param xuid: The xuid of the player. Can be None.
        :param pfid: The pfid of the player. Can be None.
        """
        logger.info(f'{Colors.YELLOW}{line}{Colors.END}')

    @events.listen('player.disconnect')
    async def on_player_disconnect(self, line: str, gamertag: str, xuid: Optional[str], pfid: Optional[str]):
        """
        When a player disconnects from the server.

        :param line: The console log line where the event occurs
        :param gamertag: The gamertag of the player
        :param xuid: The xuid of the player. Can be None.
        :param pfid: The pfid of the player. Can be None.
        """
        logger.info(f'{Colors.YELLOW}{line}{Colors.END}')

    @events.listen('backup.hold')
    async def on_backup_hold(self, line: str):
        logger.info(f'{Colors.YELLOW}{line}{Colors.END}')
        await self.send_command('save query')

    @events.listen('backup.query')
    async def on_backup_query(self, line: str, *file_list: tuple):
        logger.info(f'{Colors.YELLOW}{file_list}{Colors.END}')
        logger.debug('Backup process starting')
        await self.send_command('save resume')

    @events.listen('backup.error')
    async def on_backup_error(self, line: str):
        logger.warn(f'{Colors.YELLOW}{line}{Colors.END}')
        await self.send_command('save query')

    @events.listen('backup.resume')
    async def on_backup_resume(self, line: str):
        logger.info(f'{Colors.YELLOW}{line}{Colors.END}')
