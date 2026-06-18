from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import get_settings
import urllib.parse

settings = get_settings()

db_url = settings.DATABASE_URL
connect_args = {}

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    # Enforce SQLCipher encryption
    if "pysqlcipher" not in db_url:
        db_url = db_url.replace("sqlite://", "sqlite+pysqlcipher://")
        pwd = urllib.parse.quote_plus(settings.SECRET_KEY)
        db_url = db_url.replace("sqlite+pysqlcipher://", f"sqlite+pysqlcipher://:{pwd}@")
        if "?" in db_url:
            db_url += "&module=sqlcipher3"
        else:
            db_url += "?module=sqlcipher3"

engine = create_engine(db_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
