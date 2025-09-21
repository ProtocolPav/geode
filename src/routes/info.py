import asyncio.tasks

import sanic
from sanic import Blueprint
from sanic_ext import openapi
from sanic_ext.extensions.openapi.definitions import Response

from src.geode import Geode
from src.models.info import Info, Status, Task, TasksList, Uptime, Version

information_blueprint = Blueprint('information', '/info')

@information_blueprint.get('/')
@openapi.definition(response=[
    Response(Info.doc_schema(), status=200)
])
async def info(request, geode: Geode):
    root = [Task(name=task.get_name(), coro=task.get_coro().__qualname__) for task in asyncio.tasks.all_tasks()]
    task_list = TasksList(root=root)

    response = Info(status=geode.server.status,
                    tasks=task_list,
                    server_start=geode.server.start_time,
                    geode_start=geode.start_time,
                    minecraft_version=geode.server.version,
                    geode_version=geode.version)

    return sanic.json(response.model_dump(), default=str)

@information_blueprint.get('/tasks')
@openapi.definition(response=[
    Response(TasksList.doc_schema(), status=200)
])
async def tasks(request, geode: Geode):
    root = [Task(name=task.get_name(), coro=task.get_coro().__qualname__) for task in asyncio.tasks.all_tasks()]
    response = TasksList(root=root)
    return sanic.json(response.model_dump(), default=str)

@information_blueprint.get('/status')
@openapi.definition(response=[
    Response(Status.doc_schema(), status=200)
])
async def status(request, geode: Geode):
    response = Status(status=geode.server.status)
    return sanic.json(response.model_dump(), default=str)

@information_blueprint.get('/uptime')
@openapi.definition(response=[
    Response(Uptime.doc_schema(), status=200)
])
async def uptime(request, geode: Geode):
    response = Uptime(server_start=geode.server.start_time, geode_start=geode.start_time)
    return sanic.json(response.model_dump(), default=str)

@information_blueprint.get('/version')
@openapi.definition(response=[
    Response(Version.doc_schema(), status=200)
])
async def version(request, geode: Geode):
    response = Version(minecraft_version=geode.server.version, geode_version=geode.version)
    return sanic.json(response.model_dump(), default=str)
