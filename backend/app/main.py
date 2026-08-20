from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import storage
from app.config import settings
from app.database import Base, engine
from app.routers import invoices


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    storage.ensure_bucket()
    yield


app = FastAPI(
    title="Doku-Agent Rechnungsplattform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoices.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"app": "Doku-Agent Rechnungsplattform", "docs": "/docs"}
