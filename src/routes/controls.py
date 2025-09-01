from sanic import Blueprint

from src.geode import Geode

controls_blueprint = Blueprint('controls', '/controls')

@controls_blueprint.post('/stop')
async def stop(request, geode: Geode):
    await geode.server.stop()

@controls_blueprint.post('/start')
async def start(request, geode: Geode):
    await geode.server.start()
