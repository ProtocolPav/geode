from sanic import Blueprint, json as sanic_json

from sanic_ext import validate, openapi
from sanic_ext.extensions.openapi.definitions import RequestBody

from src.cloud_services.base import get_cloud_service
from src.geode import Geode
from src.handlers.restoration import RestorationHandler
from src.models import Message

controls_blueprint = Blueprint('controls', '/controls')

@controls_blueprint.post('/stop')
async def stop(request, geode: Geode):
    await geode.stop_server()

    return sanic_json({'response': 'Server has been stopped'})

@controls_blueprint.post('/start')
async def start(request, geode: Geode):
    await geode.start_server()

    return sanic_json({'response': 'Server has started'})

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
async def restore(request, geode: Geode):
    if geode.server.status == 'stopped':
        restoration = RestorationHandler('server/backups/hourly/test_2025-09-07_14-39-04.zip')

        await restoration.restore_backup()
        return sanic_json({'response': 'Restoring backup'})
    else:
        return sanic_json({'response': 'BAD'})

@controls_blueprint.get('/backups')
async def list_backups(request, geode: Geode):
    return sanic_json({'response': get_cloud_service().list_backups('')}, default=str)
