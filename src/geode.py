import asyncio
from datetime import datetime

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
        self.messages: list[Message] = []

        logger.info('Geode is starting...')
        logger.info(f'Running Geode {Colors.PURPLE}{self.version}{Colors.END}')
        logger.info(self.config)
        self.server = server

    async def start_server(self):
        asyncio.create_task(self.looper.start_looper(self))
        asyncio.create_task(self.server.start())

    async def stop_server(self):
        await self.server.stop()

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

    @looper.loop('Message Loop', 5, 120)
    async def message_loop(self):
        expired_message_indexes = []

        for message in self.messages:
            if datetime.now() - message.sent_time >= message.interval:
                message.sent += 1
                message.sent_time = datetime.now()
                self.server.emit(f'broadcast.{message.type}', message.content)

            if message.sent == message.repetitions:
                expired_message_indexes.append(self.messages.index(message))

        for index in expired_message_indexes:
            del self.messages[index]