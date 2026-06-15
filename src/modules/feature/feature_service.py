from src.core.base_service import BaseService
from src.modules.feature.feature_repository import FeatureRepository


class FeatureService(BaseService):
    def __init__(self):
        super().__init__(FeatureRepository())
        self.allow_filters([{"key": "name", "qt": "contains"}, {"key": "active"}])
        self.allow_search([{"key": "name"}])


feature_service = FeatureService()
