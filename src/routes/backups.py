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
from src.models.backups import BackupsList

backups_blueprint = Blueprint('backups', '/backups')

@backups_blueprint.get('/')
@openapi.definition(response=[
    Response(BackupsList.doc_schema(), status=200)
])
async def list_backups(request, geode: Geode):
    backups = get_cloud_service().list_backups(ConfigHandler()['backup']['bucket_name'])

    return sanic.json(backups.model_dump(), default=str)
