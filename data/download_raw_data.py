"""Download latest hikr.org raw data container to the local workspace."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

RAW_DIR = Path(__file__).resolve().parent / "gpx-data" / "hikr-raw-data"
RAW_CONTAINER_PREFIX = "hikeplanner-raw-data"


def _latest_container(blob_service_client: BlobServiceClient) -> str:
    """Returns the default raw data container name."""
    # Check if the container actually exists to prevent a crash later
    container_client = blob_service_client.get_container_client(RAW_CONTAINER_PREFIX)
    if not container_client.exists():
        raise SystemExit(f"Error: The container '{RAW_CONTAINER_PREFIX}' does not exist in your Azure account.")
    
    return RAW_CONTAINER_PREFIX


def download_raw_data() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path, override=True)
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        raise SystemExit(
            "Missing AZURE_STORAGE_CONNECTION_STRING in .env or environment."
        )

    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    container_name = _latest_container(blob_service_client)
    container_client = blob_service_client.get_container_client(container_name)
    blobs = list(container_client.list_blobs())
    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading raw data from {container_name} into {RAW_DIR}")
    for blob in blobs:
        download_path = RAW_DIR / blob.name
        download_path.parent.mkdir(parents=True, exist_ok=True)
        with open(download_path, "wb") as handle:
            handle.write(container_client.download_blob(blob).readall())
        print(f"Downloaded {blob.name}")
    print(f"Finished downloading {len(blobs)} files from {container_name}")


if __name__ == "__main__":
    download_raw_data()
