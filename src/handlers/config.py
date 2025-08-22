import yaml
from pathlib import Path
from collections import UserDict

class ConfigHandler(UserDict):
    def __init__(self):
        super().__init__()
        self.path = Path('./config.yml')
        self.default_path = Path('./config.default.yml')
        self._load_config()

    def _load_config(self):
        config_file = self.path if self.path.exists() else self.default_path
        with config_file.open('r') as file:
            self.data = yaml.safe_load(file) or {}
