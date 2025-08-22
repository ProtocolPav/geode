import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from sanic.log import logger, Colors

from src.handlers.config import ConfigHandler

class BackupHandler:
    def __init__(self, file_list: tuple, level_name: str):
        self.file_list = file_list
        self.level_name = level_name
        self.server_path = Path('../server/')
        self.world_path = Path('../server/worlds/')
        self.backup_path = Path('../server/backups/')
        self.backup_path.mkdir(parents=True, exist_ok=True)

        self.config = ConfigHandler()
        self.backup_location = self.config['backup']['location']
        self.bucket_name = self.config['backup']['bucket_name']

    async def backup(self):
        with tempfile.TemporaryDirectory(dir=self.backup_path) as temp_dir:
            temp_dir_path = Path(temp_dir)

            for file_name, file_length in self.file_list:
                file_path = self.world_path / Path(file_name)

                target = temp_dir_path / file_path.relative_to(self.server_path)
                target.parent.mkdir(parents=True, exist_ok=True)

                if file_path.exists():
                    shutil.copyfile(file_path, target)

                    with open(target, 'a') as f:
                        f.truncate(int(file_length))

            extra_files = []

            if self.config['backup']['include_addons']:
                extra_files = extra_files + [x for x in self.world_path.glob('**/*_packs*')]

            if self.config['backup']['include_server_files']:
                server_files = [
                    self.server_path / Path('server.properties'),
                    self.server_path / Path('allowlist.json'),
                    self.server_path / Path('permissions.json'),
                    self.server_path / Path('config/default/permissions.json'),
                    self.server_path / Path('config/default/variables.json')
                ]

                extra_files = extra_files + server_files

            for extra_file in extra_files:
                target = temp_dir_path / extra_file.relative_to(self.server_path)

                if extra_file.is_dir():
                    shutil.copytree(extra_file, target)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(extra_file, target)

            file_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            with zipfile.ZipFile(self.backup_path / Path(f'{self.level_name}_{file_date}.zip'), 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in temp_dir_path.glob('**/*'):
                    zip_file.write(file_path, file_path.relative_to(temp_dir_path))