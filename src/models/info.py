from datetime import datetime

from pydantic import Field
from sanic_ext.extensions.openapi import openapi

from src.utils.base import BaseList, BaseModel

@openapi.component()
class Status(BaseModel):
    status: str

@openapi.component()
class Task(BaseModel):
    name: str
    coro: str

@openapi.component()
class TasksList(BaseList[Task]):
    pass

@openapi.component()
class Uptime(BaseModel):
    server_start: datetime | None
    geode_start: datetime

@openapi.component()
class Version(BaseModel):
    minecraft_version: str
    geode_version: str

class Info(Status, Uptime, Version):
    tasks: TasksList
