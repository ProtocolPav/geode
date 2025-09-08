import asyncio
import uuid

from src.handlers.loop import LoopHandler
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

        asyncio.create_task(self.looper.start_looper(self), name='Looper')

        logger.info(f'Running Geode {Colors.PURPLE}{self.version}{Colors.END}')
        self.server = server

    async def start_server(self):
        if self.server.status == 'stopped':
            await self.server.start()
        else:
            raise Exception(f'Cannot start the server because of status. Expected: stopped. Current: {self.server.status}')

    async def stop_server(self):
        if self.server.status == 'started':
            await self.server.stop()
        else:
            raise Exception(f'Cannot stop the server because of status. Expected: started. Current: {self.server.status}')

    async def schedule_message(self, message: Message):
        async def send(geode: Geode):
            geode.server.emit(f'broadcast.{message.type}', message.content)

        self.looper.add_loop(send, f'Message {uuid.uuid4()}', message.interval_seconds, repetitions=message.repetitions)

    @looper.loop('Backup Loop', 3600, 60)
    async def backup_loop(self):
        await self.server.initiate_save('backup')

    @looper.loop('Map Render Loop', 3600)
    async def map_render_loop(self):
        await self.server.initiate_save('map_update')
