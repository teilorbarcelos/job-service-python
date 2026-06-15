import re

from src.core.helpers.service_helpers import build_filter_and_order, convert_value


class BaseService:
    def __init__(self, repo):
        self.repo = repo
        self._allowed_filters = {}
        self._allowed_search = {}

    def allow_filters(self, filters: list):
        self._allowed_filters = {}
        for f in filters:
            self._allowed_filters[f["key"]] = f
            snake_k = re.sub(r"(?<!^)(?=[A-Z])", "_", f["key"]).lower()
            self._allowed_filters[snake_k] = f

    def allow_search(self, search: list):
        self._allowed_search = {}
        for f in search:
            self._allowed_search[f["key"]] = f
            snake_field = re.sub(r"(?<!^)(?=[A-Z])", "_", f["key"]).lower()
            self._allowed_search[snake_field] = f

    async def find_all(self, filters=None, include=None):
        return await self.repo.search_all(filters, include)

    async def search(self, pageable: dict):
        return await self.repo.search_paginated(pageable)

    async def find_paginated(self, pageable: dict, filters=None, include=None, ordering=None):
        return await self.repo.search_paginated(pageable, filters, include, ordering)

    async def search_all_items(self):
        return await self.repo.search_all()

    async def count(self):
        return await self.repo.count_records()

    async def create(self, data: dict):
        return await self.repo.persist_record(data)

    async def update(self, id: str, data: dict):
        return await self.repo.update_record_details(id, data)

    async def delete(self, id: str):
        return await self.repo.soft_delete_record(id)

    async def set_status(self, id: str, active: bool):
        if active:
            return await self.repo.activate_record(id)
        return await self.repo.deactivate_record(id)

    async def list_items(self, filters: dict, *, ignore_default_filters: bool = False, include_deleted: bool = False):
        params = build_filter_and_order(filters, self._allowed_filters, self._allowed_search)

        if ignore_default_filters:
            params["rules"]["ignoreDefaultFilters"] = True
            if not include_deleted:
                include_deleted = convert_value(filters.get("includeDeleted", False))
            if include_deleted:
                params["rules"]["includeDeleted"] = True

        return await self.repo.search_paginated(params["pageable"], params["rules"], None, params["ordering"])

    async def list_all_items(self, filters: dict):
        return await self.list_items(filters, ignore_default_filters=True)
