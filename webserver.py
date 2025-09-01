import asyncio
import json

from sanic import Sanic, Request, HTTPResponse
from sanic_ext.extensions.openapi import openapi

from src import geode
from src.routes import blueprint_group

app = Sanic("geode")
app.config.OAS_URL_PREFIX = "/api/docs"
app.config.SWAGGER_UI_CONFIGURATION = {"docExpansion": "list"}

handler: geode.Geode


@app.before_server_start
async def init_handler(application: Sanic):
    global handler
    handler = geode.Geode()
    await handler.start_server()
    application.ext.dependency(handler)

@app.after_server_stop
async def stop_handler(application: Sanic):
    handler.server.emit('preemption')
    while handler.server.status != 'stopped':
        await asyncio.sleep(1)

app.blueprint(blueprint_group)

if __name__ == "__main__":
    #app.run(host="0.0.0.0", fast=True)
    app.run(host="0.0.0.0", dev=True)