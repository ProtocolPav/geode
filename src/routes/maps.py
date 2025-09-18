import asyncio.tasks
import os
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

maps_blueprint = Blueprint('maps', '/maps')

@maps_blueprint.get('/<layer:str>/<zoomlevel:int>/<regionx:int>/<regionz:int>/<x:int>/<z:int>')
@openapi.definition(
    response=[
        Response(
            content={"image/png": {"schema": {"type": "string", "format": "binary"}}},
            status=200,
            description="Map Tile"
        ),
        Response(status=404, description="Not found"),
    ]
)
async def get_map(request: Request, layer: str, zoomlevel: int, regionx: int, regionz: int, x: int, z: int):
    if os.path.exists(f'../unmined/{layer}/tiles/zoom.{zoomlevel}/{regionx}/{regionz}/tile.{x}.{z}.png'):
        return await sanic.file(f'../unmined/{layer}/tiles/zoom.{zoomlevel}/{regionx}/{regionz}/tile.{x}.{z}.png', mime_type='image/png')

    return sanic.empty(404)

@maps_blueprint.post('/')
@openapi.definition(
    response=Response(status=201, description="Map Render Initiated"),
    summary="Initiate a map render"
)
async def initiate_map_render(request, geode: Geode):
    await geode.initiate_save('map_update')

    return sanic.empty(status=201)
