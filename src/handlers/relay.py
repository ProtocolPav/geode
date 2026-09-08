from pathlib import Path
from typing import Literal, Optional

import httpx
from nexuscore import AuthenticatedClient
from nexuscore.api.webhook_relay import server_relay_v_1_relay_post
from nexuscore.models import RelayModel, RelayModelType


class RelayHandler:
    @classmethod
    async def _relay(cls,
                    client: AuthenticatedClient,
                    message_type: RelayModelType,
                    embed_title: str,
                    embed_content: str,
                    name: Optional[str] = "Geode"):
        await server_relay_v_1_relay_post.asyncio(client=client, body=RelayModel(
            type_=message_type,
            content='',
            embed_title=embed_title,
            embed_content=embed_content,
            name=name
        ))

    @classmethod
    async def relay_start(cls, client: AuthenticatedClient):
        version_file = Path('../server/version.geode')
        version = version_file.read_text()
        await cls._relay(client,
                         RelayModelType.START,
                        "Server Start",
                        f"The server has started. Running Minecraft Version **{version}**\n"
                                     "-# *Powered by **Geode***")

    @classmethod
    async def relay_stop(cls, client: AuthenticatedClient):
        await cls._relay(client,
                         RelayModelType.STOP,
                        "Server Stop",
                        "The server has stopped. Be patient, and it will be back up soon!\n"
                        "-# *Powered by **Geode***")

    @classmethod
    async def relay_preemption(cls, client: AuthenticatedClient):
        await cls._relay(client,
                         RelayModelType.CRASH,
                        "Server Preemption Detected",
                        "The server is shutting down to keep your builds safe and prevent world corruption!\n"
                        "-# *Powered by **Geode***")

    @classmethod
    async def relay_crash(cls, client: AuthenticatedClient):
        await cls._relay(client,
                         RelayModelType.CRASH,
                        "The Server Crashed",
                        "The server has crashed unexpectedly. Please wait for a CM to restart the server and check"
                        "that the server is okay to continue playing!\n"
                        "-# *Powered by **Geode***")

    @classmethod
    async def relay_message(cls, client: AuthenticatedClient, content: str):
        await cls._relay(client,
                         RelayModelType.OTHER,
                        "Server Message",
                        content)

    @classmethod
    async def relay_announcement(cls, client: AuthenticatedClient, content: str):
        await cls._relay(client,
                         RelayModelType.OTHER,
                        "Server Announcement",
                        content)

    @classmethod
    async def relay_backup_timeout(cls, client: AuthenticatedClient, save_type: str, duration: int):
        await cls._relay(client,
                         RelayModelType.CRASH,
                        "Backup Failed — Hold Timeout",
                        f"**Type:** `{save_type}`\n**Duration:** `{duration}s`\n"
                        f"**Action:** `save resume` was forced and the backup was **skipped** because `save query` never returned a file list. "
                        f"The held save data was discarded to prevent infinite growth.\n"
                        f"-# *Powered by **Geode***")

    @classmethod
    async def relay_backup_error(cls, client: AuthenticatedClient, title: str, content: str):
        await cls._relay(client,
                         RelayModelType.CRASH,
                        title,
                        f"{content}\n-# *Powered by **Geode***")