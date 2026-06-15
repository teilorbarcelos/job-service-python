import importlib
import logging
from typing import Any

from src.infra.storage.driver_interface import StorageDriverInterface
from src.infra.storage.drivers.local_driver import LocalDriver
from src.shared.config.settings import settings

logger = logging.getLogger(__name__)


class StorageProvider:
    def __init__(self):
        self._driver: Any = None
        self._disk = settings.storage_disk

    @property
    def driver(self) -> StorageDriverInterface:
        if self._driver is None:
            self._driver = self._resolve_driver()
        return self._driver

    def _resolve_driver(self) -> StorageDriverInterface:
        if self._disk == "local":
            return LocalDriver()

        driver_name = self._disk.capitalize()
        class_name = f"{driver_name}Driver"
        try:
            module = importlib.import_module(f"src.infra.storage.drivers.{self._disk}_driver")
            driver_class = getattr(module, class_name)
            return driver_class()
        except (ImportError, AttributeError):
            raise RuntimeError(
                f"Storage driver [{driver_name}] is not installed or implemented. "
                f"Please ensure src/infra/storage/drivers/{self._disk}_driver.py exists "
                f"with a {class_name} class."
            )

    def put(self, path: str, contents: bytes) -> None:
        self.driver.put(path, contents)

    def get(self, path: str) -> bytes:
        return self.driver.get(path)

    def delete(self, path: str) -> None:
        self.driver.delete(path)

    def exists(self, path: str) -> bool:
        return self.driver.exists(path)

    def get_url(self, path: str) -> str:
        return self.driver.get_url(path)


storage_provider = StorageProvider()
