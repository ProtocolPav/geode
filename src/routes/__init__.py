from sanic import Blueprint

from src.routes.backups import backups_blueprint
from src.routes.controls import controls_blueprint
from src.routes.info import information_blueprint

blueprints = [controls_blueprint, information_blueprint, backups_blueprint]
blueprint_group = Blueprint.group(url_prefix='/', *blueprints)