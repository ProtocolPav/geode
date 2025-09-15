import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Literal


@dataclass
class EventParser:
    name: str
    regex: re.Pattern
    check_type: Literal['match', 'findall'] = 'match'


@dataclass
class Loop:
    name: str
    callback: Callable
    task: asyncio.Task = None


@dataclass
class Message:
    content: str
    type: Literal['message', 'announcement']
    repetitions: int = 1
    interval_seconds: int = 1


@dataclass
class RestoreBackup:
    backup_path: str
    restore_type: str