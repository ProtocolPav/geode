import os

from google.cloud import storage

from .base import CloudService
from pathlib import Path

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "../google-credentials.json"

class GCloudService(CloudService):
    service = "gcloud"

    def upload_backup(self, bucket_name: str, file_path: Path, dest_path: str):
        """
        Uploads the backup file to the bucket, to the path specified.

        :param bucket_name: The name of the bucket to upload to
        :param file_path: The local path to the file to upload
        :param dest_path: The storage path to the file in the bucket
        """
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(dest_path)

        blob.upload_from_filename(file_path, if_generation_match=0)

    def download_backup(self, bucket_name: str, dest_path: Path, file_path: Path):
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(file_path)
        blob.download_to_file(dest_path)

    def list_backups(self, bucket_name: str, glob_filter: str = '*') -> list[storage.Blob]:
        """
        Returns a list of blobs in the bucket that match the glob filter

        :param bucket_name: The name of the bucket to upload to
        :param glob_filter: The glob filter to apply to the list of blobs
        """
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blobs = bucket.list_blobs(match_glob=glob_filter)
        return list(blobs)
