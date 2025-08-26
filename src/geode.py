import asyncio

from src.handlers.loops import LoopHandler
from src.models import Message
from src.server import BedrockServer
from src.handlers.config import ConfigHandler

from sanic.log import logger, Colors

class Geode:
    config: ConfigHandler = ConfigHandler()
    looper: LoopHandler = LoopHandler()
    server: BedrockServer

    def __init__(self, server: BedrockServer = BedrockServer()):
        self.version = 'v1.0'

        logger.info('Geode is starting...')
        logger.info(f'Running Geode {Colors.PURPLE}{self.version}{Colors.END}')
        logger.info(self.config)
        self.server = server

    async def start_server(self):
        asyncio.create_task(self.looper.start_looper(self), name='Looper')
        asyncio.create_task(self.server.start(), name='Server')

    async def stop_server(self):
        await self.server.stop()

    async def schedule_message(self, message: Message):
        async def send(geode: Geode):
            geode.server.emit(f'broadcast.{message.type}', message.content)

        self.looper.add_loop(send, 'Message Loop', message.interval_seconds, repetitions=message.repetitions)

    @looper.loop('Backup Loop', 3600, 60)
    async def backup_loop(self):
        if self.server.status != 'started':
            raise Exception(f'Server is not in an acceptable state to backup. Current state: {self.server.status}. Expected: started')

        self.server.emit('initiate.backup')

    @looper.loop('Map Render Loop', 3600)
    async def map_render_loop(self):
        if self.server.status != 'started':
            raise Exception(f'Server is not in an acceptable state to render a map. Current state: {self.server.status}. Expected: started')

        self.server.emit('initiate.map.render')
