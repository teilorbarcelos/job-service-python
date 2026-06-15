from src.core.base_repository import BaseRepository
from src.infra.database.db import SessionLocal
from src.infra.database.models import Product


class ProductRepository(BaseRepository[Product]):
    def __init__(self):
        super().__init__(model=Product, session_factory=SessionLocal)
