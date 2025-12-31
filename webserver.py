import asyncio
import os
import re

from sanic import Sanic
import logging.config

from src import geode
from src.routes import blueprint_group

app = Sanic("geode")
app.config.OAS_URL_PREFIX = "/api/docs"
app.config.SWAGGER_UI_CONFIGURATION = {"docExpansion": "list"}


class PlainFormatter(logging.Formatter):
    """Formatter that strips ANSI escape codes from log messages"""

    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        # Regex pattern to match ANSI escape codes
        self.ansi_escape = re.compile(r'\x1b\[[0-9;]*[A-KSTfsu]')

    def format(self, record):
        # Strip ANSI codes from the message
        record.msg = self.ansi_escape.sub('', str(record.msg))
        return super().format(record)

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'loggers': {
        'sanic.root': {
            'level': 'DEBUG',
            'handlers': ['console', 'file']
        },
        'sanic.error': {
            'level': 'INFO',
            'handlers': ['error_console'],
            'propagate': True,
            'qualname': 'sanic.error'
        },
        'sanic.access': {
            'level': 'INFO',
            'handlers': ['access_console'],
            'propagate': True,
            'qualname': 'sanic.access'
        },
        'sanic.server': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': True,
            'qualname': 'sanic.server'
        },
        'sanic.websockets': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': True,
            'qualname': 'sanic.websockets'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'generic',
            'stream': 'ext://sys.stdout',
            'level': 'INFO'  # Added level to keep console at INFO
        },
        'error_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'generic',
            'stream': 'ext://sys.stderr'
        },
        'access_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'access',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'plain',
            'filename': 'geode.log',
            'maxBytes': 10000000,
            'backupCount': 1,
            'level': 'DEBUG'
        }
    },
    'formatters': {
        'generic': {'class': 'sanic.logging.formatter.AutoFormatter'},
        'access': {'class': 'sanic.logging.formatter.AutoAccessFormatter'},
        'plain': {  # Add plain formatter without colors
            "()": PlainFormatter,
            'format': '%(asctime)s [%(levelname)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    }
})


handler: geode.Geode


@app.before_server_start
async def init_handler(application: Sanic):
    global handler
    application.ctx.preemption = False
    handler = geode.Geode()
    await handler.server.start()
    application.ext.dependency(handler)

@app.before_server_stop
async def stop_handler(application: Sanic):
    handler.server.emit('preemption')
    application.ctx.preemption = True
    while handler.server.status != 'stopped':
        await asyncio.sleep(1)

app.blueprint(blueprint_group)

if __name__ == "__main__":
    app.run(host="0.0.0.0", single_process=True)
    #app.run(host="0.0.0.0", dev=True)