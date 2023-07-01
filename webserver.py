from sanic import Sanic, Request
from sanic.response import json
from datetime import datetime
from nexus import NexusCore
import asyncio

app = Sanic("bedrock_server_app")
handler = NexusCore()


@app.route('/status')
async def status(request: Request = None):
    return json({'server_online': handler.server_running(),
                 'server_status': handler.server.status[0],
                 'update': handler.server.update})

@app.route('/status/uptime')
async def return_uptime(request: Request = None):
    return json({'server_start': f"{handler.server.start}",
                 'uptime': f"{datetime.now() - handler.server.start}"})

@app.route('/status/system_usage')
async def return_usage(request: Request):
    return json({'usage': handler.system_logs[-1]})


@app.post('/stop')
async def stop(request: Request):
    if handler.server_running():
        await handler.stop_server()

    return await status()


@app.post('/start')
async def start(request: Request):
    if not handler.server_running():
        await handler.start_server()

    return await status()


@app.route('/backup')
async def backup(request: Request):
    return json({"backup_successful": True})


@app.route('/message/<msg:str>')
async def send_message(request: Request, msg: str):
    message = msg[7:-3].replace("%20", " ")
    await handler.server.send_message(message)
    return json({'message_sent': True})

@app.route('/<gamertag:str>/give/<item:str>/<amount:int>')
async def give_item(request: Request, gamertag: str, item: str, amount: int):
    ...


@app.post('/<gamertag:str>/whitelist/add')
async def whitelist_add(request: Request, gamertag: str):
    gamertag = gamertag[12:-3].replace("%20", " ")
    await handler.server.send_command(f'whitelist add "{gamertag}"')
    return json({"gamertag_added": True})


@app.post('/<gamertag:str>/whitelist/remove')
async def whitelist_remove(request: Request, gamertag: str):
    gamertag = gamertag[12:-3].replace("%20", " ")
    await handler.server.send_command(f'whitelist remove "{gamertag}"')
    return json({"gamertag_removed": True})


# @app.post('/<gamertag:str>/promote')
# async def promote_to_operator(request: Request, gamertag: str):
#     gamertag = gamertag[12:-3].replace("%20", " ")
#     await handler.execute(f'op "{gamertag}"')
#     return json({"promoted": True})
#
#
# @app.post('/<gamertag:str>/demote')
# async def demote_to_member(request: Request, gamertag: str):
#     gamertag = gamertag[12:-3].replace("%20", " ")
#     await handler.execute(f'deop "{gamertag}"')
#     return json({"demoted": True})


@app.post('/<gamertag:str>/kick')
async def kick(request: Request, gamertag: str):
    gamertag = gamertag[12:-3].replace("%20", " ")
    await handler.server.send_command(f'kick {gamertag}')
    return json({"kicked": True})


@app.listener('after_server_start')
async def init_bdswrapper(application, loop: asyncio.AbstractEventLoop):
    await asyncio.sleep(10)
    await handler.start_server('started_by_system')

if __name__ == "__main__":
    app.run(host="0.0.0.0")
