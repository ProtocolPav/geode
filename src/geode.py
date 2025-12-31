import asyncio
from datetime import datetime

from typing_extensions import Literal

from src.handlers.loop import LoopHandler
from src.handlers.restoration import RestorationHandler
from src.handlers.usage import UsageHandler
from src.models.messages import DiscordMessage, Message
from src.server import BedrockServer
from src.handlers.config import ConfigHandler

from sanic.log import logger, Colors

class Geode:
    config: ConfigHandler = ConfigHandler()
    looper: LoopHandler = LoopHandler()
    usage: UsageHandler = UsageHandler()
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

    async def relay_discord_message(self, message: DiscordMessage):
        if len(self.server.online) > 0:
            self.server.emit(f'broadcast.discord', sender=message.sender, content=message.content)

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

    @looper.loop('Metrics Monitor', 1, 60)
    async def metrics_loop(self):
        # 1. Get CPU (Async/Non-blocking)
        cpu = await self.usage.get_cpu_percent()

        # 2. Get RAM (Async/Non-blocking)
        ram = await self.usage.get_memory_usage()

        # 3. Get Disk (Async/Non-blocking)
        disk = await self.usage.get_disk_usage()

        logger.info(f'CPU: {Colors.YELLOW}{cpu}%{Colors.END} | RAM: {Colors.PURPLE}{ram["usage_mb"]}MB ({ram["percent"]}%){Colors.END} | Disk: {Colors.RED}{disk["used_gb"]}/{disk["total_gb"]}{Colors.END}')
