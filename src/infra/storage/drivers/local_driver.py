import logging
from pathlib import Path

from src.infra.storage.driver_interface import StorageDriverInterface
from src.shared.config.settings import settings

logger = logging.getLogger(__name__)


class LocalDriver(StorageDriverInterface):
    def __init__(self, storage_path: str = None, base_url: str = None):
        self.storage_path = Path(storage_path or settings.storage_path)
        self.base_url = (base_url or settings.storage_url).rstrip("/")

        self.storage_path.mkdir(parents=True, exist_ok=True)

    def put(self, path: str, contents: bytes) -> None:
        full_path = self.storage_path / path.lstrip("/")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(full_path, "wb") as f:
                f.write(contents)
        except Exception as e:
            logger.error(f"[Storage][Local] Failed to write file to {path}: {e}")
            raise e

    def get(self, path: str) -> bytes:
        full_path = self.storage_path / path.lstrip("/")
        try:
            with open(full_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"[Storage][Local] Failed to read file from {path}: {e}")
            raise e

    def delete(self, path: str) -> None:
        full_path = self.storage_path / path.lstrip("/")
        try:
            if full_path.exists():
                full_path.unlink()
        except Exception as e:
            logger.error(f"[Storage][Local] Failed to delete file {path}: {e}")
            raise e

    def exists(self, path: str) -> bool:
        full_path = self.storage_path / path.lstrip("/")
        return full_path.exists()

    def get_url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"
