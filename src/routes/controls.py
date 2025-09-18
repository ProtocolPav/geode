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

controls_blueprint = Blueprint('controls', '/controls')

@controls_blueprint.post('/stop')
@openapi.definition(response=[
    Response(status=201, description="Server stopped"),
    Response(InternalServerError, status=500, description="Unable to stop")
])
async def stop(request, geode: Geode):
    await geode.server.stop()

    return sanic.empty(status=201)

@controls_blueprint.post('/start')
@openapi.definition(response=[
    Response(status=201, description="Server started"),
    Response(InternalServerError, status=500, description="Unable to start")
])
async def start(request, geode: Geode):
    await geode.server.start()

    return sanic.empty(status=201)

@controls_blueprint.post('/kill')
@openapi.definition(response=[
    Response(status=201, description="Server killed"),
    Response(InternalServerError, status=500, description="Unable to kill server")
])
async def kill(request, geode: Geode):
    await geode.server.kill()

    return sanic.empty(status=201)

@controls_blueprint.post('/restart')
@openapi.definition(response=[
    Response(status=201, description="Server restarted"),
    Response(InternalServerError, status=500, description="Unable to restart server")
])
async def restart(request, geode: Geode):
    await geode.restart_server()

    return sanic.empty(status=201)

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
                    # Send each line separately
                    for line in content.splitlines():
                        await response.send(f"data: {line}\n\n")
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
                            # Send each line separately
                            for line in new_content.splitlines():
                                await response.send(f"data: {line}\n\n")
                        last_size = current_size

            await asyncio.sleep(0)

    except Exception:
        pass
