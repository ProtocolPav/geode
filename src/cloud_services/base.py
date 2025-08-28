import os
import importlib
from abc import ABC, abstractmethod
from pathlib import Path


class CloudService(ABC):
    service: str

    @abstractmethod
    def upload_backup(self, bucket_name: str, file_path: Path, dest_path: str):
        pass

    @abstractmethod
    def download_backup(self, bucket_name: str, dest_path: Path, blob_name: str):
        pass

    @abstractmethod
    def list_backups(self, bucket_name: str, glob_filter: str = '*') -> list:
        pass


def get_cloud_service() -> CloudService:
    provider = os.environ.get("CLOUD_SERVICE", "local")  # default local
    module_name = f"src.cloud_services.{provider}_service"
    class_name = f"{provider.capitalize()}Service"

    module = importlib.import_module(module_name)
    cloud_service_class = getattr(module, class_name)
    return cloud_service_class()

