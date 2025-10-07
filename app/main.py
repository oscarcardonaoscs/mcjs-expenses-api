from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import Base, engine
from .core.config import settings
from .api.v1.router import api

# Crear tablas (simple para MVP; luego usa Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="MCJ Expenses API", version="1.0")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # "https://expenses.mcjscleaningservice.com",  # cuando lo publiques
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api, prefix="/v1")
