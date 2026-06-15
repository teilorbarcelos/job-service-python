from src.core.base_service import BaseService
from src.modules.product.product_repository import ProductRepository


class ProductService(BaseService):
    def __init__(self):
        super().__init__(ProductRepository())
        self.allow_filters(
            [{"key": "name", "qt": "contains"}, {"key": "sku", "qt": "equals"}, {"key": "category", "qt": "equals"}, {"key": "active"}]
        )
        self.allow_search([{"key": "name"}, {"key": "sku"}, {"key": "category"}])


product_service = ProductService()
