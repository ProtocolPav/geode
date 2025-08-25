import shutil

from .base import CloudService
from pathlib import Path

class LocalService(CloudService):
    service = "local"

    def upload_backup(self, bucket_name: str, file_path: Path, dest_path: str):
        """
        Uploads the backup file to the bucket, to the path specified.

        :param bucket_name: The name of the bucket to upload to
        :param file_path: The local path to the file to upload
        :param dest_path: The storage path to the file in the bucket
        """
        Path("../" + dest_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(file_path, f"../{dest_path}")

    def download_backup(self, bucket_name: str, dest_path: Path, file_path: Path):
        pass

    def list_backups(self, bucket_name: str, glob_filter: str = '*') -> list:
        pass
