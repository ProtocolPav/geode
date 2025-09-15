from datetime import datetime

from pydantic import Field
from sanic_ext.extensions.openapi import openapi

from src.utils.base import BaseList, BaseModel

class BackupBaseModel(BaseModel):
    full_path: str

@openapi.component()
class Backup(BackupBaseModel):
    name: str
    type: str
    timestamp: datetime
    size_bytes: int

class BackupsList(BaseList[Backup]):
    pass

class RestoreBackup(BackupBaseModel):
    restore_type: str