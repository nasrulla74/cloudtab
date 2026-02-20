from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

sync_engine = create_engine(settings.DATABASE_URL_SYNC, echo=False)
SyncSession = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)


def get_sync_db() -> Session:
    return SyncSession()
