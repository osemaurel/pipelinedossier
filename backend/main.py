"""Point d'entrée FastAPI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router
from backend.config import ROOT_DIR, get_settings
from backend.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

settings = get_settings()
app = FastAPI(
    title="Palab Dossier Generator",
    description="Génération de dossiers de collecte de démonstration.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/api/health")
async def health() -> dict[str, object]:
    """État du serveur. N'expose jamais la clé, seulement sa présence.

    Renvoie aussi la configuration d'images effectivement chargée : c'est le seul
    moyen simple de vérifier, depuis l'interface, qu'on ne fait pas tourner une
    ancienne version ou un `.env` périmé.
    """
    return {
        "status": "ok",
        "openai_configured": bool(settings.openai_api_key),
        "text_model": settings.openai_text_model,
        "image_model": settings.openai_image_model,
        "image_style": settings.openai_image_style,
        "image_size": settings.openai_image_size,
    }


# En production, l'interface compilée est servie par le même serveur que l'API :
# une seule adresse, donc pas de configuration CORS ni de second service à
# lancer. En développement, ce dossier n'existe pas et Vite prend le relais.
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    app.mount(
        "/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets"
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str) -> FileResponse:
        """Sert l'interface. Les routes /api/* sont déclarées avant et priment."""
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

    logger.info("Interface servie depuis %s", FRONTEND_DIST)
else:
    logger.info("Interface compilée absente : mode développement (Vite sur le port 3000).")
