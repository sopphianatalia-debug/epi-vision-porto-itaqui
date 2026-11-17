from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.observability import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="EPI Vision — Fase 3.1: Fusion Service", version="1.0.0")
    # A interface web (porta 8020) lê as câmeras direto do Fusion. Somente leitura é usada lá.
    # Em produção, restrinja allow_origins ao endereço real da interface.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(router, prefix=settings.api_prefix)

    @app.get("/health", tags=["health"])
    def root_health():
        return {"status": "ok"}

    return app


app = create_app()
