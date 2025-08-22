import asyncio

from src import errors
from src.handlers.loops import LoopHandler
from src.server import BedrockServer
from src.handlers.config import ConfigHandler

from sanic.log import logger, Colors

class Geode:
    config: ConfigHandler = ConfigHandler()
    looper: LoopHandler = LoopHandler()
    server: BedrockServer

    def __init__(self, server: BedrockServer = BedrockServer()):
        self.version = 'v1.0'
        self.messages: list[dict] = []

        logger.info('Geode is starting...')
        logger.info(f'Running Geode {Colors.PURPLE}{self.version}{Colors.END}')
        logger.info(self.config)
        self.server = server

    async def start_server(self):
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.looper.start_looper(self))
            tg.create_task(self.server.start())

    @looper.loop('Backup Loop', 3600)
    async def backup_loop(self):
        if self.server.status != 'started':
            raise errors.NotRunning()

        await self.server.initiate_backup()