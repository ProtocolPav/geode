from sanic import Sanic, Request
from sanic.response import json
from datetime import datetime
from bdswrapper import Handler
import asyncio

app = Sanic("bedrock_server_app")
handler = Handler()


@app.route('/status')
async def status(request: Request):
    return json({'server_online': handler.server_running(),
                 'server_status': handler.server.status,
                 'uptime': f"{datetime.now() - handler.server.start_time}",
                 'system_usage': handler.system_logs,
                 'update': handler.new_update if hasattr(handler, 'new_update') else None,
                 'logs': handler.server.logs})


@app.post('/stop')
async def stop(request: Request):
    await handler.stop_server()

    return status()


@app.post('/start')
async def start(request: Request):
    await handler.start_server()

    return status()


@app.route('/backup')
async def backup(request: Request):
    await handler.execute_backup()
    return json({"backup_successful": True})


@app.post('/<gamertag:str>/whitelist/add')
async def whitelist_add(request: Request, gamertag: str):
    gamertag = gamertag[12:-3].replace("%20", " ")
    await handler.execute_whitelist(gamertag, 'add')
    return json({"gamertag_added": True})


@app.post('/<gamertag:str>/whitelist/remove')
async def whitelist_remove(request: Request, gamertag: str):
    gamertag = gamertag[12:-3].replace("%20", " ")
    await handler.execute_whitelist(gamertag, 'remove')
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
    await handler.execute_kick(gamertag)
    return json({"kicked": True})


@app.listener('after_server_start')
async def init_bdswrapper(application, loop: asyncio.AbstractEventLoop):
    await asyncio.sleep(10)
    await handler.start_server()
    await asyncio.gather(asyncio.create_task(coro=handler.check_for_crash(),
                                             name="Handler AutoRestart"),
                         asyncio.create_task(coro=handler.log_system_usage(),
                                             name="Handler SystemLogger"))

if __name__ == "__main__":
    app.run(host="0.0.0.0")
