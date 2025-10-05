from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import Base, engine
from .core.config import settings
from .api.v1.router import api_router

# Crear tablas (simple para MVP; luego usa Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="MCJ Expenses API", version="1.0")

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],  # durante desarrollo
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/v1")
