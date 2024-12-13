from src.server import BedrockServer
from src.handlers.config import ConfigHandler

from sanic.log import logger, Colors

class Geode:
    __looper: ...
    __config: ConfigHandler
    __server: BedrockServer

    def __init__(self):
        self.version = 'v1.0'
        self.__config = ConfigHandler()
        self.messages: list[dict] = []

        logger.info('Geode is starting...')
        logger.info(f'Running Geode {Colors.PURPLE}{self.version}{Colors.END}')
        self.server: BedrockServer = BedrockServer()

    async def start_server(self):
        await self.server.start()