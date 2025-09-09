import asyncio
import shutil
import tempfile
import zipfile
from pathlib import Path

from sanic.log import logger

from src.cloud_services.base import get_cloud_service
from src.handlers.config import ConfigHandler

class RestorationHandler:
    def __init__(self, backup_name: str):
        self.server_path = Path('../server/')
        self.world_path = Path('../server/worlds/')
        self.backup_path = Path('../server/backups/')
        self.backup_path.mkdir(parents=True, exist_ok=True)

        self.backup_name = backup_name

        self.config = ConfigHandler()
        self.bucket_name = self.config['backup']['bucket_name']

        self.cloud_service = get_cloud_service()

    def __unzip_backup(self, dst: Path):
        self.cloud_service.download_backup(self.bucket_name, dst / 'download.zip', self.backup_name)

        with zipfile.ZipFile(dst / 'download.zip', 'r') as zip_ref:
            zip_ref.extractall(dst / 'restoration')

    def __copy_files(self, src: Path):
        for file in (src / 'restoration').iterdir():
            server_path_file = self.server_path / Path(file).relative_to(src / 'restoration')

            logger.debug(f'Removing {server_path_file}')
            if server_path_file.exists() and file.is_dir():
                shutil.rmtree(server_path_file, ignore_errors=True)
            elif not file.is_dir():
                server_path_file.unlink()

            logger.debug(f'Copying {file} to {server_path_file}')
            if file.is_dir():
                shutil.copytree(file, server_path_file)
            else:
                shutil.copy2(file, server_path_file)

    async def restore_backup(self):
        with tempfile.TemporaryDirectory(dir=self.backup_path) as temp_dir:
            temp_dir_path = Path(temp_dir)

            await asyncio.to_thread(self.__unzip_backup, temp_dir_path)
            await asyncio.to_thread(self.__copy_files, temp_dir_path)