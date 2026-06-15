import pytest
from src.infra.storage.drivers.{DRIVER_LOWER}_driver import {DRIVER_NAME}Driver
from src.shared.config.settings import settings

@pytest.fixture
def driver(mocker):
    {ENV_SETUP}
    {MOCK_SETUP}
    return {DRIVER_NAME}Driver()

class Test{DRIVER_NAME}Driver:
    def test_put_success(self, driver, mocker):
        mocker.patch.object(driver, "_perform_put", wraps=driver._perform_put)
        driver.put("test.txt", b"content")
        driver._perform_put.assert_called_once_with("test.txt", b"content")

    def test_put_failure(self, driver, mocker):
        mocker.patch.object(driver, "_perform_put", side_effect=Exception("Error"))
        with pytest.raises(Exception):
            driver.put("test.txt", b"content")

    def test_get_success(self, driver, mocker):
        mocker.patch.object(driver, "_perform_get", wraps=driver._perform_get)
        assert driver.get("test.txt") == b"" # Default return in template

    def test_get_failure(self, driver, mocker):
        mocker.patch.object(driver, "_perform_get", side_effect=Exception("Error"))
        with pytest.raises(Exception):
            driver.get("test.txt")

    def test_delete_success(self, driver, mocker):
        mocker.patch.object(driver, "_perform_delete", wraps=driver._perform_delete)
        driver.delete("test.txt")
        driver._perform_delete.assert_called_once_with("test.txt")

    def test_delete_failure(self, driver, mocker):
        mocker.patch.object(driver, "_perform_delete", side_effect=Exception("Error"))
        with pytest.raises(Exception):
            driver.delete("test.txt")

    def test_exists_success(self, driver, mocker):
        mocker.patch.object(driver, "_perform_exists", wraps=driver._perform_exists)
        assert driver.exists("test.txt") is False # Default return in template

    def test_exists_failure(self, driver, mocker):
        mocker.patch.object(driver, "_perform_exists", side_effect=Exception("Error"))
        with pytest.raises(Exception):
            driver.exists("test.txt")

    def test_get_url_success(self, driver, mocker):
        mocker.patch.object(driver, "_perform_get_url", wraps=driver._perform_get_url)
        assert driver.get_url("test.txt") == "" # Default return in template

    def test_get_url_failure(self, driver, mocker):
        mocker.patch.object(driver, "_perform_get_url", side_effect=Exception("Error"))
        with pytest.raises(Exception):
            driver.get_url("test.txt")
