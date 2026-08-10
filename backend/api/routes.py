"""Routes HTTP. Le frontend ne parle qu'à ce module ; la clé OpenAI reste ici."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from backend.config import Settings, get_settings
from backend.core.logging import get_logger
from backend.models.schemas import GenerationRequest, HistoryEntry, JobStatus, ValidationReport
from backend.services.excel_introspect import introspect
from backend.services.field_policy import FillMode, build_femme_specs, generated_specs
from backend.services.job_manager import JobManager

logger = get_logger(__name__)
router = APIRouter(prefix="/api")

ALLOWED_SUFFIXES = {".xlsx", ".xlsm"}
ALLOWED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel.sheet.macroEnabled.12",
    "application/octet-stream",
}
ZIP_MAGIC = b"PK\x03\x04"

# Le modèle ne porte pas de liste de pays : elle est proposée ici par défaut et
# l'utilisateur peut en saisir d'autres depuis l'interface.
DEFAULT_COUNTRIES = [
    "Bénin", "Côte d'Ivoire", "Sénégal", "Togo", "Cameroun", "Maroc",
    "Burkina Faso", "Mali", "Gabon", "Guinée", "Congo", "Tunisie",
]

_manager: JobManager | None = None


def get_manager(settings: Settings = Depends(get_settings)) -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager(settings)
    return _manager


class UploadResult(BaseModel):
    upload_id: str
    filename: str
    sheets: list[str]
    femmes_columns: int
    agents_columns: int
    photos_columns: int
    capacity: int
    text_rules: dict[str, list[int | None]]
    enums: dict[str, list[str]]
    withheld: list[str]
    default_countries: list[str] = DEFAULT_COUNTRIES


def _upload_path(settings: Settings, upload_id: str) -> Path:
    return settings.uploads_dir / f"{upload_id}.xlsx"


@router.post("/upload", response_model=UploadResult)
async def upload_model(
    file: UploadFile,
    settings: Settings = Depends(get_settings),
) -> UploadResult:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Format refusé. Déposez un classeur .xlsx ou .xlsm.",
        )
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Type de contenu refusé : {file.content_type}.",
        )

    payload = await file.read()
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fichier trop volumineux (max {settings.max_upload_bytes // (1024 * 1024)} Mo).",
        )
    if not payload.startswith(ZIP_MAGIC):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Le contenu n'est pas un classeur Excel valide.",
        )

    upload_id = uuid.uuid4().hex
    target = _upload_path(settings, upload_id)
    target.write_bytes(payload)

    try:
        schema = await asyncio.to_thread(introspect, target)
    except Exception as exc:  # noqa: BLE001 — message rendu à l'utilisateur
        target.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    specs = build_femme_specs(schema.femmes)
    enums = {
        spec.name: spec.column.allowed_values
        for spec in generated_specs(specs)
        if spec.column.allowed_values
    }
    text_rules = {
        spec.name: [spec.column.min_length, spec.column.max_length]
        for spec in generated_specs(specs)
        if spec.column.max_length
    }
    withheld = [
        spec.column.header for spec in specs if spec.mode is FillMode.WITHHELD
    ]

    logger.info("Modèle « %s » accepté (upload %s)", file.filename, upload_id)
    return UploadResult(
        upload_id=upload_id,
        filename=file.filename or "modele.xlsx",
        sheets=schema.sheet_names,
        femmes_columns=len(schema.femmes.columns),
        agents_columns=len(schema.agents.columns),
        photos_columns=len(schema.photos.columns) if schema.photos else 0,
        capacity=schema.femmes.capacity,
        text_rules=text_rules,
        enums=enums,
        withheld=withheld,
    )


@router.post("/jobs", response_model=JobStatus)
async def create_job(
    request: GenerationRequest,
    settings: Settings = Depends(get_settings),
    manager: JobManager = Depends(get_manager),
) -> JobStatus:
    source = _upload_path(settings, request.upload_id)
    if not source.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Modèle introuvable. Téléversez à nouveau le fichier Excel.",
        )
    job = manager.start(request, source)
    return job.status


@router.post("/jobs/{job_id}/resume", response_model=JobStatus)
async def resume_job(job_id: str, manager: JobManager = Depends(get_manager)) -> JobStatus:
    """Reprend un job interrompu sans régénérer ce qui est déjà produit."""
    try:
        job = manager.resume(job_id)
    except KeyError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Aucun point de contrôle pour ce job."
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Le modèle d'origine n'est plus disponible. Téléversez-le à nouveau.",
        ) from exc
    return job.status


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str, manager: JobManager = Depends(get_manager)) -> JobStatus:
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job inconnu.")
    return job.status


@router.get("/jobs/{job_id}/events")
async def stream_events(
    job_id: str, manager: JobManager = Depends(get_manager)
) -> StreamingResponse:
    """Progression en temps réel (Server-Sent Events)."""
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job inconnu.")

    async def event_stream() -> AsyncIterator[str]:
        queue = job.subscribe()
        try:
            yield f"data: {job.status.model_dump_json()}\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=20.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {payload}\n\n"
                state = json.loads(payload)
                if state.get("stage") in {"done", "error"}:
                    break
        finally:
            job.unsubscribe(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/jobs/{job_id}/report", response_model=ValidationReport)
async def get_report(job_id: str, manager: JobManager = Depends(get_manager)) -> ValidationReport:
    job = manager.get(job_id)
    if job is None or job.status.report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Rapport indisponible.")
    return job.status.report


def _download(job_id: str, filename: str | None, manager: JobManager) -> FileResponse:
    job = manager.get(job_id)
    if job is None or not filename:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Fichier indisponible.")
    path = job.output_dir / filename
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Fichier introuvable sur le serveur.")
    return FileResponse(path, filename=filename)


@router.get("/jobs/{job_id}/download/excel")
async def download_excel(
    job_id: str, manager: JobManager = Depends(get_manager)
) -> FileResponse:
    job = manager.get(job_id)
    return _download(job_id, job.status.excel_filename if job else None, manager)


@router.get("/jobs/{job_id}/download/zip")
async def download_zip(job_id: str, manager: JobManager = Depends(get_manager)) -> FileResponse:
    job = manager.get(job_id)
    return _download(job_id, job.status.zip_filename if job else None, manager)


@router.get("/history", response_model=list[HistoryEntry])
async def get_history(manager: JobManager = Depends(get_manager)) -> list[HistoryEntry]:
    return manager.history()
