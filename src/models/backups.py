from datetime import datetime

from pydantic import Field
from sanic_ext.extensions.openapi import openapi

from src.utils.base import BaseList, BaseModel

@openapi.component()
class Backup(BaseModel):
    full_path: str
    name: str
    type: str
    timestamp: datetime
    size_bytes: int

class BackupsList(BaseList[Backup]):
    pass
