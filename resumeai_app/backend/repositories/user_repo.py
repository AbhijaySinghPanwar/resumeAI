"""
backend/repositories/user_repo.py — Data access layer for User.

All database logic is here. Services call repositories; routers call services.
No raw SQL or SQLAlchemy queries should appear in routers.
"""
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session

from database.models import User
from core.logger import get_logger

logger = get_logger(__name__)


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, name: str, email: str, password_hash: str) -> User:
        user = User(name=name, email=email, password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info("User created: id=%d email=%s", user.id, user.email)
        return user

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def email_exists(self, email: str) -> bool:
        return self.db.query(User.id).filter(User.email == email).first() is not None

    def deactivate(self, user_id: int) -> bool:
        user = self.get_by_id(user_id)
        if not user:
            return False
        user.is_active = False
        self.db.commit()
        return True
