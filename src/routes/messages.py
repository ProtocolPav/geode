import sanic
from sanic import Blueprint
from sanic_ext import openapi, validate
from sanic_ext.extensions.openapi.definitions import RequestBody, Response

from src.geode import Geode
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
