from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.server import BedrockServer


class BdsAdapter:
    """Thin adapter over BedrockServer for command-response pattern.
    
    Option A: wraps BedrockServer.send_command + wait_for (Future over pyventus emit).
    Option B future: replace wait_for body with Queue, keep same interface.
    """

    def __init__(self, server: "BedrockServer"):
        self._server = server

    async def send(self, command: str, sleep: int = 0):
        await self._server.send_command(command, sleep)

    async def wait_for(self, event: str, timeout: float):
        return await self._server.wait_for(event, timeout)

    async def execute(self, command: str, expect: str, timeout: float):
        """Send command and wait for expected event."""
        await self.send(command)
        return await self.wait_for(expect, timeout)
