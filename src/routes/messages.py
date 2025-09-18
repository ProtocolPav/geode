import asyncio.tasks
from pathlib import Path

from google.api_core.exceptions import InternalServerError
import sanic
from sanic import Request, Blueprint

from sanic_ext import validate, openapi
from sanic_ext.extensions.openapi.definitions import RequestBody, Response

from src.cloud_services.base import get_cloud_service
from src.geode import Geode
from src.handlers.config import ConfigHandler
from src.handlers.restoration import RestorationHandler
from src.models.backups import BackupsList, RestoreBackup
from src.models.messages import DiscordMessage, Message

messages_blueprint = Blueprint('messages', '/messages')

@messages_blueprint.post('/schedule')
@openapi.definition(
    body=RequestBody(Message, required=True),
    response=Response(status=201, description="Message Scheduled"),
    summary="Schedule a message"
)
@validate(json=Message)
async def schedule_message(request, geode: Geode, body: Message):
    await geode.schedule_message(body)

    return sanic.empty(status=201)

@messages_blueprint.post('/discord')
@openapi.definition(
    body=RequestBody(DiscordMessage, required=True),
    response=Response(status=201, description="Message Sent"),
    summary="Send a message from Discord to the Server"
)
@validate(json=DiscordMessage)
async def discord_message(request, geode: Geode, body: DiscordMessage):
    await geode.relay_discord_message(body)

    return sanic.empty(status=201)
