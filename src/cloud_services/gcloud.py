import os

from google.cloud import storage

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "../google-credentials.json"

def upload_backup(bucket_name: str, source_file_name: os.PathLike[str], destination_blob_name):
    """
    Uploads the backup file to the bucket, to the path specified.

    :param bucket_name: The name of the bucket to upload to
    :param source_file_name: The local path to the file to upload
    :param destination_blob_name: The storage path to the file in the bucket
    """

    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name, if_generation_match=0)
