import os
import importlib
from abc import ABC, abstractmethod
from pathlib import Path

from src.models.backups import BackupsList


class CloudService(ABC):
    service: str

    @abstractmethod
    def upload_backup(self, bucket_name: str, backup_path: Path, cloud_dest_path: str):
        pass

    @abstractmethod
    def download_backup(self, bucket_name: str, local_dest_path: Path, cloud_backup_name: str):
        pass

    @abstractmethod
    def list_backups(self, bucket_name: str, glob_filter: str = '*') -> BackupsList:
        pass


def get_cloud_service() -> CloudService:
    provider = os.environ.get("CLOUD_SERVICE", "local")  # default local
    module_name = f"src.cloud_services.{provider}_service"
    class_name = f"{provider.capitalize()}Service"

    module = importlib.import_module(module_name)
    cloud_service_class = getattr(module, class_name)
    return cloud_service_class()

