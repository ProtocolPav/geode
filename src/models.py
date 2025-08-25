import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal


@dataclass
class EventParser:
    name: str
    regex: re.Pattern
    check_type: Literal['match', 'findall'] = 'match'


@dataclass
class Message:
    content: str
    type: Literal['message', 'announcement']
    sent_time: datetime
    repetitions: int = 1
    sent: int = 0
    interval: timedelta = timedelta(minutes=1)