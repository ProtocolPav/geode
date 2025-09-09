import asyncio.tasks
from pathlib import Path

from sanic import Request, Blueprint, json as sanic_json

from sanic_ext import validate, openapi
from sanic_ext.extensions.openapi.definitions import RequestBody

from src.cloud_services.base import get_cloud_service
from src.geode import Geode
from src.handlers.config import ConfigHandler
from src.handlers.restoration import RestorationHandler
from src.models import Message, RestoreBackup

controls_blueprint = Blueprint('controls', '/controls')

@controls_blueprint.post('/stop')
async def stop(request, geode: Geode):
    await geode.server.stop()

    return sanic_json({'response': 'Server has been stopped'})

@controls_blueprint.post('/start')
async def start(request, geode: Geode):
    await geode.server.start()

    return sanic_json({'response': 'Server has started'})

@controls_blueprint.post('/kill')
async def kill(request, geode: Geode):
    await geode.server.kill()

    return sanic_json({'response': 'Server has been killed'})

@controls_blueprint.get('/tasks')
async def tasks(request, geode: Geode):
    return sanic_json({'response': [task.get_name() for task in asyncio.tasks.all_tasks()]}, default=str)

@controls_blueprint.post('/message')
@openapi.definition(
    body=RequestBody(Message, required=True),
    summary="Schedule a server message"
)
@validate(json=Message)
async def schedule_message(request, geode: Geode, body: Message):
    await geode.schedule_message(body)

    return sanic_json({'response': 'Scheduled message'})

@controls_blueprint.post('/restore')
@openapi.definition(
    body=RequestBody(RestoreBackup, required=True),
    summary="Restore a backup"
)
@validate(json=RestoreBackup)
async def restore(request, geode: Geode, body: RestoreBackup):
    await geode.restore_backup(body.backup_path)
    return sanic_json({'response': 'Restored backup'})

@controls_blueprint.get('/backups')
async def list_backups(request, geode: Geode):
    return sanic_json({'response': get_cloud_service().list_backups(ConfigHandler()['backup']['bucket_name'])}, default=str)


@controls_blueprint.get('/logs')
async def log_tail(request: Request, geode: Geode):
    response = await request.respond(content_type="text/event-stream")
    log_file = Path('./geode.log')
    last_size = 0

    try:
        if log_file.exists():
            with log_file.open() as file:
                content = file.read()
                if content:
                    await response.send(f"{content}")
                last_size = file.tell()

        while not request.transport.is_closing() and not request.app.ctx.preemption:
            if log_file.exists():
                current_size = log_file.stat().st_size

                if current_size < last_size:
                    last_size = 0

                if current_size > last_size:
                    with log_file.open() as file:
                        file.seek(last_size)
                        new_content = file.read()
                        if new_content:
                            await response.send(f"{new_content}")
                        last_size = current_size

            await asyncio.sleep(0)

    except Exception:
        pass

