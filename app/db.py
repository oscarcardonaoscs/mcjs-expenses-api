from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .core.config import settings
import ssl

ssl_context = ssl.create_default_context()
# (Opcional en Windows) si llegara a fallar con cert_verify:
# ssl_context.check_hostname = False
# ssl_context.verify_mode = ssl.CERT_NONE  # ⚠️ Solo si estás desarrollando localmente

engine = create_engine(
    settings.DB_URL,
    pool_pre_ping=True,
    connect_args={
        "ssl": {
            "ssl": ssl_context,
        }
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
