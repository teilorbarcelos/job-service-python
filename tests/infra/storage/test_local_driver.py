import pytest
import os
import shutil
from pathlib import Path
from src.infra.storage.drivers.local_driver import LocalDriver


@pytest.fixture
def temp_storage(tmp_path):
    storage_path = tmp_path / "storage"
    return storage_path


@pytest.fixture
def local_driver(temp_storage):
    return LocalDriver(storage_path=str(temp_storage), base_url="http://test-storage")


class TestLocalDriver:
    def test_put_and_get(self, local_driver, temp_storage):
        path = "test.txt"
        contents = b"hello world"
        local_driver.put(path, contents)

        assert (temp_storage / path).exists()
        assert local_driver.get(path) == contents

    def test_put_creates_directories(self, local_driver, temp_storage):
        path = "subdir/test.txt"
        contents = b"nested hello"
        local_driver.put(path, contents)

        assert (temp_storage / "subdir" / "test.txt").exists()
        assert local_driver.get(path) == contents

    def test_exists(self, local_driver):
        path = "exists.txt"
        local_driver.put(path, b"data")

        assert local_driver.exists(path) is True
        assert local_driver.exists("non-existent.txt") is False

    def test_delete(self, local_driver):
        path = "delete.txt"
        local_driver.put(path, b"data")
        assert local_driver.exists(path) is True

        local_driver.delete(path)
        assert local_driver.exists(path) is False

    def test_delete_non_existent_does_not_fail(self, local_driver):
        local_driver.delete("not-here.txt")

    def test_get_url(self, local_driver):
        assert local_driver.get_url("file.jpg") == "http://test-storage/file.jpg"
        assert local_driver.get_url("/file.jpg") == "http://test-storage/file.jpg"

    def test_put_error(self, local_driver, mocker):

        mocker.patch("builtins.open", side_effect=IOError("Write failed"))
        with pytest.raises(IOError):
            local_driver.put("error.txt", b"data")

    def test_get_error(self, local_driver, mocker):
        mocker.patch("builtins.open", side_effect=IOError("Read failed"))
        with pytest.raises(IOError):
            local_driver.get("error.txt")

    def test_delete_error(self, local_driver, mocker):
        mocker.patch("pathlib.Path.unlink", side_effect=OSError("Delete failed"))

        mocker.patch("pathlib.Path.exists", return_value=True)
        with pytest.raises(OSError):
            local_driver.delete("error.txt")
