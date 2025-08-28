from pathlib import Path

from src.cloud_services.base import get_cloud_service
from src.handlers.config import ConfigHandler

class RestorationHandler:
    def __init__(self, level_name: str, backup_name: str):
        self.level_name = level_name
        self.server_path = Path('../server/')
        self.world_path = Path('../server/worlds/')
        self.backup_path = Path('../server/backups/')
        self.backup_path.mkdir(parents=True, exist_ok=True)

        self.backup_name = backup_name

        self.config = ConfigHandler()
        self.bucket_name = self.config['backup']['bucket_name']

        self.cloud_service = get_cloud_service()

    def __unzip_backup(self, dst: Path):
        self.cloud_service.download_backup(self.bucket_name, dst, self.backup_name)

        
