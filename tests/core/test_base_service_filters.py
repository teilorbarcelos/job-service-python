import pytest
from src.core.base_service import BaseService
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock


class MockRepo:
    def __init__(self):
        self.search_paginated = AsyncMock()


@pytest.mark.asyncio
class TestBaseServiceFilters:
    async def test_should_allow_valid_filters(self):
        repo = MockRepo()
        service = BaseService(repo)
        service.allow_filters([{"key": "name", "qt": "contains"}])

        filters = {"name": "test", "page": 0, "size": 10}
        await service.list_items(filters)

        repo.search_paginated.assert_called_once()
        args = repo.search_paginated.call_args[0]
        assert args[1]["andRules"][0]["key"] == "name"
        assert args[1]["andRules"][0]["search"] == "test"

    async def test_should_raise_400_for_invalid_filter(self):
        repo = MockRepo()
        service = BaseService(repo)
        service.allow_filters([{"key": "name"}])

        filters = {"invalid_key": "test"}
        with pytest.raises(HTTPException) as exc:
            await service.list_items(filters)
        assert exc.value.status_code == 400
        assert "não é permitido" in exc.value.detail

    async def test_should_allow_valid_search_fields(self):
        repo = MockRepo()
        service = BaseService(repo)
        service.allow_search([{"key": "name"}, {"key": "email"}])

        filters = {"searchWord": "test", "searchFields": "name,email", "page": 0, "size": 10}
        await service.list_items(filters)

        args = repo.search_paginated.call_args[0]
        assert len(args[1]["orRules"]) == 2
        assert args[1]["orRules"][0]["key"] == "name"
        assert args[1]["orRules"][1]["key"] == "email"

    async def test_should_raise_400_for_invalid_search_field(self):
        repo = MockRepo()
        service = BaseService(repo)
        service.allow_search([{"key": "name"}])

        filters = {"searchWord": "test", "searchFields": "invalid_field"}
        with pytest.raises(HTTPException) as exc:
            await service.list_items(filters)
        assert exc.value.status_code == 400
        assert "não está disponível para pesquisa global" in exc.value.detail

    async def test_should_raise_400_if_searchWord_without_searchFields(self):
        repo = MockRepo()
        service = BaseService(repo)

        filters = {"searchWord": "test"}
        with pytest.raises(HTTPException) as exc:
            await service.list_items(filters)
        assert exc.value.status_code == 400
        assert 'searchFields" é obrigatório' in exc.value.detail

    async def test_should_handle_non_string_value_with_date_operator(self):
        repo = MockRepo()
        service = BaseService(repo)
        service.allow_filters([{"key": "age"}])

        filters = {"age_start": "20"}
        await service.list_items(filters)

        args = repo.search_paginated.call_args[0]
        assert args[1]["andRules"][0]["search"] == 20
        assert args[1]["andRules"][0]["qt"] == "gte"
