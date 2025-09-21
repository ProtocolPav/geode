import os

import sanic
from sanic import Blueprint, Request
from sanic_ext import openapi
from sanic_ext.extensions.openapi.definitions import Response

from src.geode import Geode

maps_blueprint = Blueprint('maps', '/maps')

# For serving the default Unmined Web HTML, if wanted
maps_blueprint.static("/webpage/", "../unmined/", index="index.html", name="webpage")

@maps_blueprint.get("/webpage")
@openapi.definition(
    summary="Default Unmined Web UI",
    description="Serves the default Unmined generated HTML (and related static assets).",
    response=[
        Response(
            status=200,
            content={"text/html": {"schema": {"type": "string"}}},
            description="Unmined Web HTML"
        ),
        Response(status=404, description="Not found")
    ]
)
async def webpage_placeholder(_):
    # This is just so OpenAPI sees it — Sanic's static handler will actually serve the content
    return sanic.text("This route is served statically, see ../unmined/")


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
