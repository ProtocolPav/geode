import yaml
from pathlib import Path

class ConfigHandler(dict):
    def __init__(self):
        super().__init__()
        self.path = Path('./config.ymla')
        self.default_path = Path('./config.default.yml')

        self.__load_config()

    def __load_config(self):
        if self.path.exists():
            file = self.path.open('r')
        else:
            file = self.default_path.open('r')

        self.__dict__ = yaml.safe_load(file)
