import asyncio
from datetime import datetime

from typing_extensions import Literal

from src.handlers.loop import LoopHandler
from src.handlers.restoration import RestorationHandler
from src.models.messages import DiscordMessage, Message
from src.server import BedrockServer
from src.handlers.config import ConfigHandler
from src.services.backup_coordinator import BackupCoordinator

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
        # Coordinator owns backup hold lifecycle (global hold, retries, timeout, relay)
        # Easiest for future Option B: coordinator wraps BdsAdapter.wait_for, not direct emit
        self.backup_coordinator = BackupCoordinator(server)

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
        # Delegate to coordinator — single owner for hold→query→backup→resume
        # Coordinator handles global hold lock, status alias, timeouts, retries, relay, and ensures resume
        result = await self.backup_coordinator.run(save_type)
        if result.type == 'skipped' and result.reason == 'concurrent':
            # Keep API compat: previously raised Exception on concurrent; now raise for callers that expect it
            raise Exception(f'Server cannot launch a {save_type}. A save is already in progress ({self.server.status})')
        if result.type == 'failed':
            raise Exception(f'Backup {save_type} failed: {result.reason}')
        # On skipped hold_timeout, we do NOT raise — skip backup as requested, hold already resumed
        return result

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

    @looper.loop('Backup Loop', 3600, 30)
    async def backup_loop(self):
        await self.initiate_save('backup')

    # Temporary change - map Updates to happen every 2.5 hours
    @looper.loop('Map Render Loop', 3600*2.5, 90)
    async def map_render_loop(self):
        await self.initiate_save('map_update')
