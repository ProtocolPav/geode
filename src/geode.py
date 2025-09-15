import asyncio
from datetime import datetime

from typing_extensions import Literal

from src.handlers.loop import LoopHandler
from src.handlers.restoration import RestorationHandler
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
        self.start_time = datetime.now()

        asyncio.create_task(self.looper.start_looper(self), name='Looper')

        logger.info(f'Running Geode {Colors.PURPLE}{self.version}{Colors.END}')
        self.server = server

    async def schedule_message(self, message: Message):
        async def send(geode: Geode):
            geode.server.emit(f'broadcast.{message.type}', message.content)

        message_id = f"{message.content[:40].strip()}... ({message.interval_seconds} seconds) ({message.repetitions} reps)"
        self.looper.add_loop(send, f'Message {message_id}', message.interval_seconds, repetitions=message.repetitions)

    async def restart_server(self):
        await self.server.stop()

        while self.server.status != 'stopped':
            await asyncio.sleep(1)

        await self.server.start()

    async def initiate_save(self, save_type: Literal['backup', 'map_update']):
        if self.server.status != 'started':
            raise Exception(f'Server cannot launch a {save_type}. Current state: {self.server.status}. Expected: started')

        await self.server.send_command('save hold')
        self.server.status = save_type

    async def restore_backup(self, backup_path: str):
        logger.info(f'Restoring backup {Colors.YELLOW}{backup_path}{Colors.END}')
        logger.info('Backing up current save...')
        await self.initiate_save('backup')

        while self.server.status != 'started':
            await asyncio.sleep(1)

        logger.info('Backup complete. Stopping server...')
        await self.server.stop()

        while self.server.status != 'stopped':
            await asyncio.sleep(1)

        logger.info('Downloading and applying the restored backup...')
        restoration_handler = RestorationHandler(backup_path)
        await restoration_handler.restore_backup()

        logger.info('Backup restoration complete.')
        await self.server.start()

    @looper.loop('Backup Loop', 3600, 60)
    async def backup_loop(self):
        await self.initiate_save('backup')

    @looper.loop('Map Render Loop', 3600)
    async def map_render_loop(self):
        await self.initiate_save('map_update')
