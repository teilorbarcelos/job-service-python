import pytest
from src.infra.storage.storage_provider import StorageProvider
from src.infra.storage.drivers.local_driver import LocalDriver
from src.shared.config.settings import settings


class TestStorageProvider:
    def test_resolve_local_driver(self):
        settings.storage_disk = "local"
        provider = StorageProvider()
        assert isinstance(provider.driver, LocalDriver)

    def test_delegate_methods_to_driver(self, mocker):
        settings.storage_disk = "local"
        provider = StorageProvider()

        mock_driver = mocker.patch.object(provider, "_driver")

        provider.put("path", b"contents")
        mock_driver.put.assert_called_once_with("path", b"contents")

        provider.get("path")
        mock_driver.get.assert_called_once_with("path")

        provider.delete("path")
        mock_driver.delete.assert_called_once_with("path")

        provider.exists("path")
        mock_driver.exists.assert_called_once_with("path")

        provider.get_url("path")
        mock_driver.get_url.assert_called_once_with("path")

    def test_resolve_unimplemented_driver_raises_error(self):
        settings.storage_disk = "nonexistent"
        provider = StorageProvider()
        with pytest.raises(RuntimeError) as exc:
            _ = provider.driver
        assert "Storage driver [Nonexistent] is not installed" in str(exc.value)

    def test_dynamic_loading_success(self, mocker):

        settings.storage_disk = "mock"
        provider = StorageProvider()

        mock_driver_instance = mocker.Mock()
        mock_driver_class = mocker.Mock(return_value=mock_driver_instance)

        mock_module = mocker.Mock()

        setattr(mock_module, "MockDriver", mock_driver_class)

        mocker.patch("importlib.import_module", return_value=mock_module)

        assert provider.driver == mock_driver_instance
