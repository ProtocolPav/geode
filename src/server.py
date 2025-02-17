import asyncio.subprocess
import asyncio
import platform
from src import installation
from pathlib import Path

from sanic.log import logger, Colors

from src.handlers.events import EventHandler


class BedrockServer:
    __process: asyncio.subprocess.Process | None
    __tasks: asyncio.TaskGroup
    __events: EventHandler = EventHandler()

    def __init__(self):
        if platform.system().lower() == 'linux':
            self.executable = './bedrock_server'
        else:
            raise OSError('Geode only supports Debian-based Linux distributions, we advise you to run Geode via Docker.')

        self.__process = None

    async def __send_command(self, command: str, sleep: int = 0):
        logger.debug(f'Running Command {Colors.BLUE}{command}{Colors.END}')
        self.__process.stdin.write(f'{command}\n'.encode())
        await self.__process.stdin.drain()
        await asyncio.sleep(sleep)

    async def __server_output(self):
        """
        Process server output and fire any necessary events
        """
        while True:
            line = (await self.__process.stdout.readline()).decode().rstrip()
            line = '] '.join(line.split('] ')[1:])

            parsed_line = self.__events.parse(line)

            if parsed_line is not None:
                await parsed_line.callback(self, line, *parsed_line.args)
            elif line:  # Won't print empty lines
                logger.info(line)

    @__events.listen('server.start')
    async def on_server_start(self, line: str):
        logger.info(f'{Colors.YELLOW}{line}{Colors.END}')

    @__events.listen('server.stop')
    async def on_server_stop(self, line: str):
        logger.info(f'{Colors.YELLOW}{line}{Colors.END}')
        # Clean up pending tasks, like the server output, etc.

    @__events.listen('server.version')
    async def on_server_version(self, line: str, version: str):
        logger.info(f'{Colors.BOLD}{Colors.PURPLE}{line}{Colors.END}')
        version_file = Path('../server/version.geode')
        version_file.write_text(version)

    @__events.listen('player.connect')
    async def on_player_connect(self, line: str, gamertag: str, xuid: str):
        logger.info(f'{Colors.YELLOW}{line}{Colors.END}')

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
            # TO ADD: Disconnect all connected players
            await self.__send_command('stop')
