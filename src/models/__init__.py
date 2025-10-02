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
    print_type: Literal['full', 'ignore'] = 'full'


@dataclass
class Loop:
    name: str
    callback: Callable
    task: asyncio.Task = None
