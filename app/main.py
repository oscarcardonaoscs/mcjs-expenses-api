from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import Base, engine
from .core.config import settings
from .api.v1.router import api
import os

app = FastAPI(
    title="MCJ Expenses API",
    version="1.0",
    docs_url="/v1/docs",
    redoc_url=None,
    openapi_url="/v1/openapi.json",
)

# Crea tablas SOLO en desarrollo/MVP
if os.getenv("ENV", "dev") != "prod":
    Base.metadata.create_all(bind=engine)

# CORS
FRONTEND_ORIGIN = "https://expenses.mcjscleaningservice.com"
LOCAL_ORIGIN = "http://localhost:5173"  # útil para pruebas locales

allow_origins = [FRONTEND_ORIGIN]
if os.getenv("ENV", "dev") != "prod":
    allow_origins.append(LOCAL_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,  # pon True si usas cookies o credentials en fetch
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api, prefix="/v1")
