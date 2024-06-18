import httpx
from sanic import Sanic, Request
from sanic.response import json, text
from datetime import datetime, timedelta
from amethyst import Amethyst
import asyncio

app = Sanic("bedrock_server_app")
handler = Amethyst()


@app.route('/<text_test:strorempty>')
async def default(request: Request, text_test: str):
    return text(f"Webserver ok. Text send: {text_test}. {request.args}")


@app.route('/amethyst/version')
async def version(request: Request):
    return text(f"{handler.version}")


@app.route('/server/details')
async def status(request: Request = None):
    return json({'server_online': handler.server.running(),
                 'server_status': handler.server.status[0],
                 'status_check': handler.server.status_check(),
                 'update': handler.server.update,
                 'server_start': f"{handler.server.start}",
                 'uptime': f"{datetime.now() - handler.server.start}",
                 'usage': handler.system_logs[-1],
                 'last_backup': f"{handler.previous_backup}"})


@app.route('/server/stop')
async def stop(request: Request):
    await handler.stop_server()
    return await status()


@app.route('/server/start')
async def start(request: Request):
    await handler.start_server()
    return await status()


@app.route('/server/preempt')
async def preempt(request: Request):
    await handler.server.set_status('preemption')
    return await status()


@app.route('/server/backup')
async def backup(request: Request):
    await handler.server.send_command('save hold', sleep=5)
    await handler.server.send_command('save query', sleep=10)
    await handler.server.send_command('save resume')
    return json({"backup_successful": True})


@app.route('/server/update')
async def update(request: Request):
    if handler.server.running():
        return json({'response': 'Error. Server is running!'})

    else:
        await handler.server.check_for_updates()
        return json({'response': handler.server.update})


@app.route('/commands/message')
async def message(request: Request):
    if request.args.get('msg', []):
        await handler.server.send_message(request.args['msg'][0])
        return text('Message has been sent!')
    else:
        return text('Please include msg as an argument. Example: thorny-bds:8000/commands/message?msg=Hello!!!!')


@app.route('/commands/message/schedule')
async def schedule_message(request: Request):
    interval = int(request.args.get('interval', '7200'))
    count = int(request.args.get('count', '5'))

    if request.args.get('msg', None):
        handler.messages.append({'content': request.args['msg'][0],
                                 'type': 'message',
                                 'time': datetime.now()})
        for i in range(1, count-1):
            handler.messages.append({'content': request.args['msg'][0],
                                     'type': 'message',
                                     'time': datetime.now() + timedelta(seconds=interval*i)})

        handler.messages.sort(key=lambda x: x['time'])

        return text(f'Message has been scheduled to be sent {count} times. Once every {interval} seconds.')
    else:
        return text('Please include msg as an argument. Example: thorny-bds:8000/commands/message/schedule?msg=Hello!!!!')


@app.route('/commands/announce')
async def announce(request: Request):
    if request.args.get('msg', None):
        await handler.server.send_announce(request.args['msg'][0])
        return text('Announcement has been sent!')
    else:
        return text('Please include msg as an argument. Example: thorny-bds:8000/commands/announce?msg=Hello!!!!')


@app.route('/commands/quest/progress')
async def quest_progress(request: Request):
    if request.args.get('player', None):
        player = request.args.get('player', None)
        progress = request.args.get('progress', 'Quest Progress Unavailable')

        await handler.server.send_command(f'title {player} actionbar {progress}')
        await handler.server.send_command(f'execute at {player} run playsound note.pling @p ~ ~3 ~ 100 1.5')
        await asyncio.sleep(0.2)
        await handler.server.send_command(f'execute at {player} run playsound note.pling @p ~ ~3 ~ 100 2')

        return text("OK!")
    else:
        return text('Please include player as an argument. Example: thorny-bds:8000/commands/announce?msg=Hello!!!!')


@app.route('/commands/quest/complete')
async def quest_complete(request: Request):
    if request.args.get('player', None):
        player = request.args.get('player', '')
        playername = player.replace('"', '')
        reward = request.args.get('reward', None)
        reward_count = request.args.get('reward_count', 1)

        await handler.server.send_command(f'title {player} title Quest Complete')
        await handler.server.send_command(f'execute at {player} run playsound random.levelup @p ~ ~3 ~ 100 1.5')
        if reward:
            await handler.server.send_command(f'give {player} {reward} {reward_count}')
        await handler.server.send_message(f'§e+=+=+=+=+=+=+ Server Message +=+=+=+=+=+=+§r\\n'
                                          f'{playername} has just completed a Quest! '
                                          f'Run §d/quests view§r on the discord to accept and start your own quest!')
        await handler.server.send_announce(f'{playername} has just completed a Quest!')

        # async with httpx.AsyncClient() as client:
        #     r = await client.post('http://thorny-wbs:8000/chat/event', timeout=None,
        #                           data={'content': f"{playername} has just completed a Quest!",
        #                                 'colour': 'yellow'})

        return text("OK!")
    else:
        return text('Please include player as an argument. Example: thorny-bds:8000/commands/announce?msg=Hello!!!!')


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


@app.route('/kick/<gamertag:str>')
async def kick(request: Request, gamertag: str):
    gamertag = gamertag.replace("%20", " ")
    await handler.server.send_command(f'kick "{gamertag}"')
    return json(await server_response())


@app.listener('after_server_start')
async def init_core(application, loop: asyncio.AbstractEventLoop):
    await asyncio.sleep(10)
    await handler.start_server('started_by_system')


@app.listener('before_server_stop')
async def stop_core(application, loop: asyncio.AbstractEventLoop):
    handler.server.set_status('preemption')
    await asyncio.sleep(3)

if __name__ == "__main__":
    app.run(host="0.0.0.0", access_log=False)
