import asyncio.subprocess
import asyncio
import platform
from src import installation

from sanic.log import logger


class BedrockServer:
    __process: asyncio.subprocess.Process | None
    __tasks: asyncio.TaskGroup
    __events: ...

    def __init__(self):
        if platform.system().lower() == 'linux':
            self.executable = './bedrock_server'
        else:
            raise OSError('Geode only supports Debian-based Linux distributions, we advise you to run Geode via Docker.')

        self.__process = None

    async def __send_command(self, command: str, sleep: int = 0):
        logger.debug(f'Running Command [bold frame sandy_brown]{command}')
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

            if not line:
                pass
            elif "Quit correctly" in line:
                logger.info(line)
                break
            else:
                logger.info(line)

    async def start(self):
        if not self.__process:
            logger.debug(f'Checking for updates...')
            await installation.download()

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
            # Disconnect all connected players
            await self.__send_command('stop')
