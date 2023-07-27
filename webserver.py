from sanic import Sanic, Request
from sanic.response import json, text
from datetime import datetime
from nexus import NexusCore
import asyncio

app = Sanic("bedrock_server_app")
handler = NexusCore()


@app.route('/<text_test:strorempty>')
async def default(request: Request, text_test: str):
    return text(f"Webserver ok. Text send: {text_test}")

@app.route('/server/details')
async def status(request: Request = None):
    return json({'server_online': handler.server_running(),
                 'server_status': handler.server.status[0],
                 'status_check': handler.server_status_check(),
                 'update': handler.server.update,
                 'server_start': f"{handler.server.start}",
                 'uptime': f"{datetime.now() - handler.server.start}",
                 'usage': handler.system_logs[-1],
                 'last_backup': f"{handler.previous_backup}"})

@app.route('/stop')
async def stop(request: Request):
    await handler.stop_server()
    return await status()


@app.route('/start')
async def start(request: Request):
    await handler.start_server()
    return await status()


@app.route('/server/backup')
async def backup(request: Request):
    await handler.server.send_command('save hold', sleep=5)
    await handler.server.send_command('save query', sleep=5)
    await handler.server.send_command('save resume')
    return json({"backup_successful": True})


@app.route('/server/update')
async def update(request: Request):
    if handler.server_running():
        return json({'response': 'Error. Server is running!'})

    else:
        await handler.server.check_for_updates()
        return json({'response': handler.server.update})


@app.route('/commands/message/<msg:str>')
async def message(request: Request, msg: str):
    content = msg.replace("%20", " ").replace("%C2%A7", "§")
    await handler.server.send_message(content)
    return json({'message_sent': True})


@app.route('/commands/announce/<msg:str>')
async def announce(request: Request, msg: str):
    content = msg.replace("%20", " ").replace("%C2%A7", "§")
    await handler.server.send_announce(content)
    return json({'message_sent': True})


async def server_response(request: Request = None):
    await asyncio.sleep(0.3)
    return {'response': handler.server.console_logs[-1]}


@app.route('/commands/give/<gamertag:str>/<item:str>/<amount:int>')
async def give_item(request: Request, gamertag: str, item: str, amount: int):
    gamertag = gamertag.replace("%20", " ")
    await handler.server.send_command(f'give "{gamertag}" {item} {amount}')
    return json(await server_response())


@app.route('/commands/clear/<gamertag:str>/<item:str>/<amount:int>')
async def clear(request: Request, gamertag: str, item: str, amount: int):
    gamertag = gamertag.replace("%20", " ")
    await handler.server.send_test_for('name="%s", hasitem={item=%s, quantity=%s..}' % (gamertag, item, amount))

    response = await server_response()

    if gamertag in response['response']:
        await handler.server.send_command(f'clear "{gamertag}" {item} 0 {amount}')

    return json(await server_response())


@app.route('/whitelist/add/<gamertag:str>')
async def whitelist_add(request: Request, gamertag: str):
    gamertag = gamertag.replace("%20", " ")
    await handler.server.send_command(f'whitelist add "{gamertag}"')
    return json(await server_response())


@app.route('/whitelist/remove/<gamertag:str>')
async def whitelist_remove(request: Request, gamertag: str):
    gamertag = gamertag.replace("%20", " ")
    await handler.server.send_command(f'whitelist remove "{gamertag}"')
    return json(await server_response())


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


@app.route('/kick/<gamertag:str>')
async def kick(request: Request, gamertag: str):
    gamertag = gamertag.replace("%20", " ")
    await handler.server.send_command(f'kick "{gamertag}"')
    return json(await server_response())


@app.listener('after_server_start')
async def init_core(application, loop: asyncio.AbstractEventLoop):
    await asyncio.sleep(10)
    await handler.start_server('started_by_system')

if __name__ == "__main__":
    app.run(host="0.0.0.0", access_log=False)
