from sanic import Blueprint

from sanic_ext import validate, openapi
from sanic_ext.extensions.openapi.definitions import RequestBody

from src.geode import Geode
from src.handlers.restoration import RestorationHandler
from src.models import Message

controls_blueprint = Blueprint('controls', '/controls')

@controls_blueprint.post('/stop')
async def stop(request, geode: Geode):
    await geode.server.stop()

@controls_blueprint.post('/start')
async def start(request, geode: Geode):
    await geode.server.start()

@controls_blueprint.post('/message')
@openapi.definition(
    body=RequestBody(Message, required=True),
    summary="User profile update"
)
@validate(json=Message)
async def schedule_message(request, geode: Geode, body: Message):
    await geode.schedule_message(body)

@controls_blueprint.post('/restore')
async def restore(request, geode: Geode):
    restoration = RestorationHandler('dsadsa', 'server/backups/hourly/test_2025-09-02_17-12-47.zip')

    await restoration.restore_backup()