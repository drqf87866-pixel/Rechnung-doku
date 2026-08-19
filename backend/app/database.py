from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

url = make_url(settings.database_url)
is_sqlite = url.drivername == "sqlite"
is_postgres = url.drivername.startswith("postgres")

connect_args = {"check_same_thread": False} if is_sqlite else {}

engine_kwargs = {}
if is_postgres:
    query = dict(url.query)
    query.setdefault("sslmode", "require")
    url = url.set(query=query)
    engine_kwargs = {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 0}

engine = create_engine(url, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
