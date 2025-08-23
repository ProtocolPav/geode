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

    def __copy_files_to_dir(self, dst: Path):
        """
        Copies files to the specified destination directory.
        The copied files will also be truncated to the specified length by the Bedrock Server.

        :param dst: The destination directory path.
        """
        for file_name, file_length in self.file_list:
            file_path = self.world_path / Path(file_name)

            target = dst / file_path.relative_to(self.server_path)
            target.parent.mkdir(parents=True, exist_ok=True)

            if file_path.exists():
                shutil.copyfile(file_path, target)

                with open(target, 'a') as f:
                    f.truncate(int(file_length))

    def __copy_extra_files(self, dst: Path):
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
            target = dst / extra_file.relative_to(self.server_path)

            if extra_file.is_dir():
                shutil.copytree(extra_file, target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(extra_file, target)

    def __zip_files(self, src: Path):
        file_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        destination = self.backup_path / Path(f'{self.level_name}_{file_date}.zip')

        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in src.glob('**/*'):
                zip_file.write(file_path, file_path.relative_to(src))

    def __run_unmined(self):
        ...

    async def backup(self):
        with tempfile.TemporaryDirectory(dir=self.backup_path) as temp_dir:
            temp_dir_path = Path(temp_dir)

            self.__copy_files_to_dir(temp_dir_path)
            self.__copy_extra_files(temp_dir_path)
            self.__zip_files(temp_dir_path)

    async def map_update(self):
        with tempfile.TemporaryDirectory(dir=self.backup_path) as temp_dir:
            temp_dir_path = Path(temp_dir)
            self.__copy_files_to_dir(temp_dir_path)
