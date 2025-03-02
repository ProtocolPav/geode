import asyncio
import re
from dataclasses import dataclass
from collections.abc import Callable

from sanic.log import logger, Colors

@dataclass
class EventParser:
    name: str
    regex: re.Pattern

@dataclass
class ParsedEvent:
    name: str
    callback: Callable
    args: tuple | list | None

class EventHandler:
    def __init__(self):
        self.events = [
            EventParser('player.connect', re.compile(r'Player connected: (.*), xuid: ([1-9]+)', re.IGNORECASE)),
            EventParser('player.spawn',
                        re.compile(r'Player Spawned: (.*), xuid: ([1-9]+)(?:, pfid: ([a-z0-9]+))?', re.IGNORECASE)),
            EventParser('player.disconnect',
                        re.compile(r'Player disconnected: (.*), xuid: ([1-9]+)(?:, pfid: ([a-z0-9]+))?', re.IGNORECASE)),
            EventParser('server.start', re.compile(r'^Server started', re.IGNORECASE)),
            EventParser('server.stop', re.compile(r'^Quit correctly', re.IGNORECASE)),
            EventParser('server.version', re.compile(r'^Version:?\s*(\d+\.\d+\.\d+\.\d+)$', re.IGNORECASE)),
            EventParser('backup.hold', re.compile(r'Saving', re.IGNORECASE)),
            EventParser('backup.hold.error', re.compile(r'The command is already running', re.IGNORECASE)),
            EventParser('backup.query', re.compile(r'(.*/[^/]+:\d+)', re.IGNORECASE)),
            EventParser('backup.error', re.compile(r'A previous save has not been completed', re.IGNORECASE)),
            EventParser('backup.resume', re.compile(r'Changes to the world are resumed', re.IGNORECASE)),
        ]
        self.listeners: dict[str, Callable] = {}

        for x in self.events:
            self.listeners[x.name] = self.__default

    def parse(self, line) -> ParsedEvent | None:
        for event in self.events:
            if event.name == 'backup.query':
                matches = event.regex.findall(line)
                if matches:
                    return ParsedEvent(event.name, self.listeners[event.name], matches)
            elif match := event.regex.search(line):
                return ParsedEvent(event.name, self.listeners[event.name], match.groups())
        return None

    def listen(self, event: str):
        def decorator(func: Callable):
            if event in [x.name for x in self.events]:
                self.listeners[event] = func
                logger.info(f'Registered Event {event} with callback as {func.__name__}')
            else:
                logger.info(f'Cannot register Event {event}! Does not exist')

        return decorator

    # REDUNDANT METHOD?
    async def emit(self, event: str, *args):
        if self.listeners.get(event, None):
            await self.listeners[event](args)
        else:
            logger.info(f'The Event {event} is not registered.')

    @staticmethod
    async def __default(self, line: str, *args):
        logger.info(f'{Colors.GREEN}{line}{Colors.END}  <- Event not registered, args: {args}')
