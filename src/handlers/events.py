import asyncio
import re
from dataclasses import dataclass
from collections.abc import Callable
from typing import Literal

from sanic.log import logger, Colors

@dataclass
class EventParser:
    name: str
    regex: re.Pattern | None = None
    check_type: Literal['match', 'findall', 'manual'] = 'match'

@dataclass
class ParsedEvent:
    name: str
    callback: Callable
    args: tuple | list | None

class EventHandler:
    def __init__(self):
        self.events = [
            # Player Events
            EventParser('player.connect', re.compile(r'Player connected: (.*), xuid: ([1-9]+)', re.IGNORECASE)),
            EventParser('player.spawn', re.compile(r'Player Spawned: (.*), xuid: ([1-9]+)(?:, pfid: ([a-z0-9]+))?', re.IGNORECASE)),
            EventParser('player.disconnect', re.compile(r'Player disconnected: (.*), xuid: ([1-9]+)(?:, pfid: ([a-z0-9]+))?', re.IGNORECASE)),

            # Server Events
            EventParser('server.start', re.compile(r'^Server started', re.IGNORECASE)),
            EventParser('server.stop', re.compile(r'^Quit correctly', re.IGNORECASE)),
            EventParser('server.stop', re.compile(r'^Exiting program', re.IGNORECASE)),
            EventParser('server.crash', re.compile(r'^Killed', re.IGNORECASE)),
            EventParser('server.crash', re.compile(r'^Crash', re.IGNORECASE)),
            EventParser('server.version', re.compile(r'^Version:?\s*(\d+\.\d+\.\d+\.\d+)$', re.IGNORECASE)),

            # Backup Events
            EventParser('backup.hold', re.compile(r'Saving', re.IGNORECASE)),
            EventParser('backup.hold.error', re.compile(r'The command is already running', re.IGNORECASE)),
            EventParser('backup.query', re.compile(r'(?:^|,\s*)([^:]+):(\d+)(?=\s*(?:,|$))', re.IGNORECASE), 'findall'),
            EventParser('backup.error', re.compile(r'A previous save has not been completed', re.IGNORECASE)),
            EventParser('backup.resume', re.compile(r'Changes to the world are resumed', re.IGNORECASE)),

            # Manual Events (Invoked via .emit())
            # Currently does not work as expected, as the self
            # parameter of the listener ends up being not the server class
            EventParser('initiate.backup', check_type='manual'),
            EventParser('initiate.map.render', check_type='manual'),
            EventParser('preemption', check_type='manual'),
        ]
        self.listeners: dict[str, Callable] = {}

        for x in self.events:
            self.listeners[x.name] = self.__default

    def parse(self, line) -> ParsedEvent | None:
        """
        Parses a log line to match events and extract relevant data.

        This method processes a given log line by iterating through the list of Events.
        If a match is found using regular expressions associated with an event,
        it returns a `ParsedEvent`.

        Parameters:
            line: str
                The line from the log that needs to be parsed.

        Returns:
            ParsedEvent | None
                A `ParsedEvent` object with the event details if a match is found, or
                None if no match is found.
        """
        for event in self.events:
            if event.check_type == 'manual':
                return None

            elif event.check_type == 'findall':
                matches = event.regex.findall(line)
                if matches:
                    return ParsedEvent(event.name, self.listeners[event.name], matches)

            elif match := event.regex.search(line):
                return ParsedEvent(event.name, self.listeners[event.name], match.groups())
        return None

    def listen(self, event: str):
        """
        Registers a callback function for a specific event.

        Parameters:
        event: str
            The name of the event to associate with the given callback function.

        Returns:
        Callable
            A decorator function that registers the callback function for
            the given event.
        """
        def decorator(func: Callable):
            if event in [x.name for x in self.events]:
                self.listeners[event] = func
                logger.info(f'Registered Event {event} with callback as {func.__name__}')
            else:
                logger.info(f'Cannot register Event {event}! Does not exist')

        return decorator

    async def emit(self, event: str, *args):
        """
        Emit an event to the corresponding registered listener.

        This function triggers the execution of the registered listener for the
        given event.
        """
        if self.listeners.get(event, None):
            await self.listeners[event](*args)
        else:
            logger.info(f'The Event {event} is not registered.')

    @staticmethod
    async def __default(self, line: str, *args):
        logger.info(f'{Colors.GREEN}{line}{Colors.END}  <- Event not registered, args: {args}')
