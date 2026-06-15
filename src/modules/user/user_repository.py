from src.core.base_repository import BaseRepository
from src.infra.database.db import SessionLocal
from src.infra.database.models import User


class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(model=User, session_factory=SessionLocal)
