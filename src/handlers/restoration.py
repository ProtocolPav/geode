import tempfile
import zipfile
from pathlib import Path

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
        self.cloud_service.download_backup(self.bucket_name, dst / self.backup_name, self.backup_name)

        with zipfile.ZipFile(dst / self.backup_name, 'r') as zip_ref:
            zip_ref.extractall(dst / 'restoration')

    async def restore_backup(self):
        with tempfile.TemporaryDirectory(dir=self.backup_path) as temp_dir:
            temp_dir_path = Path(temp_dir)

            self.__unzip_backup(temp_dir_path)