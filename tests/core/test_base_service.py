import pytest

from src.core.base_service import BaseService
from src.core.helpers.service_helpers import convert_value, parse_date_value


class MockRepo:
    def __init__(self, mocker):
        self.search_paginated = mocker.AsyncMock()
        self.search_all = mocker.AsyncMock()
        self.count_records = mocker.AsyncMock()
        self.persist_record = mocker.AsyncMock()
        self.update_record_details = mocker.AsyncMock()
        self.soft_delete_record = mocker.AsyncMock()
        self.activate_record = mocker.AsyncMock()
        self.deactivate_record = mocker.AsyncMock()
        self.find_one_by_id = mocker.AsyncMock()


class MockService(BaseService):
    def __init__(self, repo):
        super().__init__(repo)
        self.allow_filters([{"key": "name"}])
        self.allow_search([{"key": "name"}])


@pytest.fixture
def mock_repo(mocker):
    return MockRepo(mocker)


@pytest.fixture
def service(mock_repo):
    return MockService(mock_repo)


@pytest.mark.asyncio
class TestBaseService:
    async def test_should_call_repository_search_paginated(self, service, mock_repo):
        mock_repo.search_paginated.return_value = {"items": [], "total": 0, "page": 0, "size": 10}
        await service.search({"page": 0, "size": 10})
        mock_repo.search_paginated.assert_called()

    async def test_should_call_repository_search_all(self, service, mock_repo):
        mock_repo.search_all.return_value = []
        await service.search_all_items()
        mock_repo.search_all.assert_called()

    async def test_should_call_find_all(self, service, mock_repo):
        mock_repo.search_all.return_value = []
        await service.find_all()
        mock_repo.search_all.assert_called()

    async def test_should_call_find_paginated(self, service, mock_repo):
        mock_repo.search_paginated.return_value = {"items": []}
        await service.find_paginated({"page": 0})
        mock_repo.search_paginated.assert_called()

    async def test_should_call_repository_count_records(self, service, mock_repo):
        mock_repo.count_records.return_value = 10
        await service.count()
        mock_repo.count_records.assert_called()

    async def test_should_call_repository_persist_record(self, service, mock_repo):
        mock_repo.persist_record.return_value = {}
        await service.create({})
        mock_repo.persist_record.assert_called()

    async def test_should_call_repository_update_record_details(self, service, mock_repo):
        mock_repo.update_record_details.return_value = {}
        await service.update("1", {})
        mock_repo.update_record_details.assert_called()

    async def test_should_call_repository_soft_delete_record(self, service, mock_repo):
        mock_repo.soft_delete_record.return_value = {}
        await service.delete("1")
        mock_repo.soft_delete_record.assert_called()

    async def test_should_call_activate_record_when_set_status_is_true(self, service, mock_repo):
        mock_repo.activate_record.return_value = {}
        await service.set_status("1", True)
        mock_repo.activate_record.assert_called()

    async def test_should_call_deactivate_record_when_set_status_is_false(self, service, mock_repo):
        mock_repo.deactivate_record.return_value = {}
        await service.set_status("1", False)
        mock_repo.deactivate_record.assert_called()

    async def test_should_throw_bad_request_error_if_filter_not_allowed(self, service):
        with pytest.raises(Exception, match="Filtro 'unknown' não é permitido"):
            await service.list_items({"unknown": "val"})

    async def test_should_handle_search_word_in_list_items(self, service, mock_repo):
        mock_repo.search_paginated.return_value = {"items": [], "total": 0, "page": 0, "size": 10}
        await service.list_items({"searchWord": "test", "searchFields": "name"})
        mock_repo.search_paginated.assert_called()

    async def test_should_call_repository_search_paginated_with_ignore_default_filters(self, service, mock_repo):
        mock_repo.search_paginated.return_value = {"items": [], "total": 0, "page": 0, "size": 10}
        await service.list_all_items({"page": 0, "size": 10, "name": "Test"})
        mock_repo.search_paginated.assert_called()
        call_args = mock_repo.search_paginated.call_args[0]
        assert any(r["key"] == "name" and r["search"] == "Test" for r in call_args[1]["andRules"])

    async def test_convert_value_helpers(self):
        assert convert_value("100") == 100
        assert convert_value("-10") == -10
        assert convert_value("10.5") == 10.5
        assert convert_value("true") is True
        assert convert_value("hello") == "hello"

    async def test_parse_date_value_invalid_date(self):
        invalid_date = "2020-13-45"
        assert parse_date_value(invalid_date, qt="equals") == invalid_date

    async def test_parse_date_value_operators(self):
        date_str = "2023-01-01"
        assert "00:00:00" in str(parse_date_value(date_str, qt="gte"))
        assert "23:59:59" in str(parse_date_value(date_str, qt="lte"))

    async def test_build_filter_date_range_extended(self, service):
        from datetime import datetime

        from src.core.helpers.service_helpers import build_filter_and_order

        filters = {"created_at_start": "2023-01-01", "created_at_end": "2023-01-02"}
        params = build_filter_and_order(filters, {"created_at": {"key": "created_at"}}, {})
        rules = params["rules"]["andRules"]
        start_rule = next(r for r in rules if r["qt"] == "gte")
        end_rule = next(r for r in rules if r["qt"] == "lte")
        assert isinstance(start_rule["search"], datetime)
        assert isinstance(end_rule["search"], datetime)

    async def test_list_all_items_extended(self, service, mock_repo):
        mock_repo.search_paginated.return_value = {"items": []}
        result = await service.list_all_items({"includeDeleted": "true"})
        assert "items" in result
        mock_repo.search_paginated.assert_called_once()

    async def test_parse_date_value_iso_extended(self):
        iso_str = "2023-01-01T12:00:00Z"
        res = parse_date_value(iso_str, "equals")
        assert res.hour == 12

    async def test_build_filter_camel_case_dates_extended(self, service):
        from src.core.helpers.service_helpers import build_filter_and_order

        filters = {"nameStart": "2023-01-01", "nameEnd": "2023-01-02"}
        params = build_filter_and_order(filters, {"name": {"key": "name"}}, {})
        rules = params["rules"]["andRules"]
        assert any(r["qt"] == "gte" for r in rules)
        assert any(r["qt"] == "lte" for r in rules)

    async def test_parse_date_value_not_matching_re_extended(self):
        from src.core.helpers.service_helpers import parse_date_value

        val = "not-a-date-at-all"
        assert parse_date_value(val, "equals") == val

    async def test_parse_date_value_invalid_date_range_raises(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            parse_date_value("2020-13-45", qt="gte")
        assert exc.value.status_code == 400

    async def test_parse_date_value_invalid_iso_range_raises(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            parse_date_value("invalid-iso", qt="gte")
        assert exc.value.status_code == 400

    async def test_build_filter_ignores_special_keys(self):
        from src.core.helpers.service_helpers import build_filter_and_order

        filters = {"ignoreDefaultFilters": "true", "includeDeleted": "true", "name": "Value"}
        res = build_filter_and_order(filters, {"name": {"key": "name"}}, {})
        assert "ignoreDefaultFilters" not in [r["key"] for r in res["rules"]["andRules"]]
        assert "includeDeleted" not in [r["key"] for r in res["rules"]["andRules"]]

    async def test_build_filter_orderby_validation(self):
        from fastapi import HTTPException

        from src.core.helpers.service_helpers import build_filter_and_order

        res = build_filter_and_order({"orderBy": "name"}, {"name": {"key": "name"}}, {"email": {"key": "email"}})
        assert res["ordering"]["orderBy"] == "name"

        with pytest.raises(HTTPException) as exc:
            build_filter_and_order({"orderBy": "invalid_col"}, {"name": {"key": "name"}}, {"email": {"key": "email"}})
        assert exc.value.status_code == 400

    async def test_build_filter_size_limit(self):
        from fastapi import HTTPException

        from src.core.helpers.service_helpers import build_filter_and_order

        with pytest.raises(HTTPException) as exc:
            build_filter_and_order({"size": "101"}, {}, {})
        assert exc.value.status_code == 400

    async def test_build_filter_missing_search_fields_raises(self):
        from fastapi import HTTPException

        from src.core.helpers.service_helpers import build_filter_and_order

        with pytest.raises(HTTPException) as exc:
            build_filter_and_order({"searchWord": "test"}, {}, {})
        assert exc.value.status_code == 400
