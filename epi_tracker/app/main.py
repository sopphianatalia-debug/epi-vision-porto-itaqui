from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="EPI Vision - Tracker Service (Fase 3.8)", version="1.0.0")
    # CORS (Fase 3.8B, seção 3): o frontend roda em outra origem/porta.
    # Liberado amplamente porque este serviço não expõe dado sensível
    # (nenhuma biometria, nenhum PII além de employee_id já usado em
    # texto claro por todo o sistema) — mesma politica de exposição que
    # os outros serviços FastAPI do projeto já tinham implicitamente ao
    # não restringir CORS nenhum deles.
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )
    app.include_router(router, prefix=settings.api_prefix)

    @app.get("/health", tags=["health"])
    def root_health():
        return {"status": "ok"}

    return app


app = create_app()
