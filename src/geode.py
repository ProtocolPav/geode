import asyncio

from src.handlers.loops import LoopHandler
from src.server import BedrockServer
from src.handlers.config import ConfigHandler

from sanic.log import logger, Colors

class Geode:
    config: ConfigHandler = ConfigHandler()
    __looper: LoopHandler = LoopHandler()
    __server: BedrockServer

    def __init__(self):
        self.version = 'v1.0'
        self.messages: list[dict] = []

        logger.info('Geode is starting...')
        logger.info(f'Running Geode {Colors.PURPLE}{self.version}{Colors.END}')
        self.server: BedrockServer = BedrockServer()

    async def start_server(self):
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.__looper.start_looper(self))
            tg.create_task(self.server.start())

    @__looper.loop('Backup Loop', 3600)
    async def backup_loop(self):
        if self.config['backup']['enabled']:
            ...