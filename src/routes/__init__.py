from sanic import Blueprint
from src.routes.controls import controls_blueprint

blueprints = [controls_blueprint]
blueprint_group = Blueprint.group(url_prefix='/', *blueprints)