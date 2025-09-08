import os
from typing import Iterator

from google.cloud import storage

from .base import CloudService
from pathlib import Path

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "../google-credentials.json"

class GcloudService(CloudService):
    service = "gcloud"

    def upload_backup(self, bucket_name: str, backup_path: Path, cloud_dest_path: str):
        """
        Uploads the backup file specified in backup_path to the path specified in cloud_dest_path.

        :param bucket_name: The name of the bucket to upload to
        :param backup_path: The local path to the file to upload
        :param cloud_dest_path: The storage path to the file in the bucket
        """
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(cloud_dest_path)

        blob.upload_from_filename(backup_path, if_generation_match=0)

    def download_backup(self, bucket_name: str, local_dest_path: Path, cloud_backup_name: str):
        """
        Downloads the backup file from Google Cloud, specified by cloud_backup_name to the local_dest_path.

        :param bucket_name: The name of the bucket to download from
        :param local_dest_path: The local path to the file to download
        :param cloud_backup_name: The storage path to the file in the bucket
        """
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(cloud_backup_name)
        blob.download_to_file(local_dest_path)

    def list_backups(self, bucket_name: str, glob_filter: str = '**/**/*.zip') -> list[str]:
        """
        Returns a list of blobs in the bucket that match the glob filter

        :param bucket_name: The name of the bucket to upload to
        :param glob_filter: The glob filter to apply to the list of blobs
        """
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blobs: Iterator[storage.Blob] = bucket.list_blobs(match_glob=glob_filter)
        return [blob.name for blob in blobs]
