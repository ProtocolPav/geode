import shutil

from .base import CloudService
from pathlib import Path

class LocalService(CloudService):
    service = "local"

    def upload_backup(self, bucket_name: str, backup_path: Path, cloud_dest_path: str):
        """
        Uploads the backup file specified in backup_path to the path specified in cloud_dest_path.

        :param bucket_name: Not used for Local Backup
        :param backup_path: The local path to the file to upload
        :param cloud_dest_path: The storage path to the file in the bucket
        """
        Path("../" + cloud_dest_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(backup_path, f"../{cloud_dest_path}")

    def download_backup(self, bucket_name: str, local_dest_path: Path, cloud_backup_name: str):
        """
        Downloads the backup file from the path specified in cloud_backup_name to the local_dest_path.

        :param bucket_name: Not used for Local Backup
        :param local_dest_path: The local path to the file to download
        :param cloud_backup_name: The storage path to the file in the bucket
        """
        Path(f"../{local_dest_path}").parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(f"../{cloud_backup_name}", local_dest_path)

    def list_backups(self, bucket_name: str, glob_filter: str = '*') -> list:
        pass
