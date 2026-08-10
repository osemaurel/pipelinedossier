"""Orchestration des jobs de génération.

Un job survit à la fermeture de la page : il s'exécute côté serveur et son état
est écrit sur disque après chaque étape coûteuse. Un job interrompu reprend au
dernier point de contrôle plutôt que de tout régénérer.
"""

from __future__ import annotations

import asyncio
import json
import random
from datetime import date, datetime
from pathlib import Path
from typing import Any

from backend.config import Settings, get_settings
from backend.core.logging import get_logger
from backend.models.schemas import (
    STAGE_LABELS,
    Agent,
    GenerationRequest,
    HistoryEntry,
    JobStage,
    JobStatus,
    PhotoRow,
    Profile,
    ValidationReport,
)
from backend.services.excel_introspect import WorkbookSchema, introspect
from backend.services.excel_service import ExcelWriter
from backend.services.field_policy import build_agent_specs, build_femme_specs
from backend.services.image_generator import ImageGenerator
from backend.services.openai_service import OpenAIService
from backend.services.profile_generator import ProfileGenerator, assign_agents
from backend.services.validation_service import Validator
from backend.services.zip_service import build_archive

logger = get_logger(__name__)

STAGE_ORDER = [
    JobStage.ANALYSE, JobStage.AGENTS, JobStage.PROFILS, JobStage.VALIDATION,
    JobStage.AVATARS, JobStage.EXCEL, JobStage.ZIP,
]


def new_job_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    suffix = "".join(random.choices("0123456789ABCDEF", k=4))
    return f"JOB-{stamp}-{suffix}"


class Job:
    """État vivant d'une génération, avec diffusion des changements aux clients."""

    def __init__(self, job_id: str, request: GenerationRequest, settings: Settings) -> None:
        self.status = JobStatus(
            job_id=job_id,
            stage=JobStage.QUEUED,
            stage_label=STAGE_LABELS[JobStage.QUEUED],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            profiles_total=request.profile_count,
            avatars_total=request.profile_count * request.avatars_per_profile,
            request=request,
        )
        self.request = request
        self.work_dir = settings.temp_dir / job_id
        self.output_dir = settings.outputs_dir / job_id
        self.photos_dir = self.work_dir / "photos"
        self._subscribers: list[asyncio.Queue[str]] = []

    @property
    def state_file(self) -> Path:
        return self.work_dir / "state.json"

    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def publish(self) -> None:
        self.status.updated_at = datetime.now()
        payload = self.status.model_dump_json()
        for queue in list(self._subscribers):
            queue.put_nowait(payload)

    def enter(self, stage: JobStage, message: str | None = None) -> None:
        if self.status.stage in STAGE_ORDER and self.status.stage not in self.status.completed_stages:
            self.status.completed_stages.append(self.status.stage.value)
        self.status.stage = stage
        self.status.stage_label = STAGE_LABELS[stage]
        if message:
            self.status.messages.append(message)
            logger.info("%s — %s", self.status.job_id, message)
        self.publish()

    def fail(self, error: str) -> None:
        self.status.stage = JobStage.ERROR
        self.status.stage_label = STAGE_LABELS[JobStage.ERROR]
        self.status.error = error
        logger.error("%s en échec : %s", self.status.job_id, error)
        self.publish()

    # -- points de contrôle -------------------------------------------------

    def save_checkpoint(self, agents: list[Agent], profiles: list[Profile]) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "job_id": self.status.job_id,
            "request": self.request.model_dump(),
            "agents": [a.model_dump() for a in agents],
            "profiles": [p.model_dump() for p in profiles],
        }
        self.state_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def load_checkpoint(self) -> tuple[list[Agent], list[Profile]]:
        if not self.state_file.exists():
            return [], []
        try:
            payload: dict[str, Any] = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return [], []
        agents = [Agent(**item) for item in payload.get("agents", [])]
        profiles = [Profile(**item) for item in payload.get("profiles", [])]
        if agents or profiles:
            logger.info(
                "%s : reprise sur point de contrôle (%d agents, %d profils déjà générés)",
                self.status.job_id, len(agents), len(profiles),
            )
        return agents, profiles


class JobManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._jobs: dict[str, Job] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._history_file = self._settings.outputs_dir / "history.json"

    # -- accès -------------------------------------------------------------

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def history(self) -> list[HistoryEntry]:
        entries = [
            HistoryEntry(
                job_id=job.status.job_id,
                created_at=job.status.created_at,
                stage=job.status.stage,
                profiles=job.status.report.profiles if job.status.report else 0,
                agents=job.status.report.agents if job.status.report else 0,
                avatars=job.status.report.avatars if job.status.report else 0,
                excel_filename=job.status.excel_filename,
                zip_filename=job.status.zip_filename,
            )
            for job in self._jobs.values()
        ]
        stored = self._load_history()
        known = {entry.job_id for entry in entries}
        entries.extend(entry for entry in stored if entry.job_id not in known)
        return sorted(entries, key=lambda item: item.created_at, reverse=True)

    def _load_history(self) -> list[HistoryEntry]:
        if not self._history_file.exists():
            return []
        try:
            raw = json.loads(self._history_file.read_text(encoding="utf-8"))
            return [HistoryEntry(**item) for item in raw]
        except (json.JSONDecodeError, OSError, ValueError):
            return []

    def _persist_history(self) -> None:
        payload = [json.loads(entry.model_dump_json()) for entry in self.history()]
        self._history_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # -- exécution ---------------------------------------------------------

    def start(self, request: GenerationRequest, source: Path) -> Job:
        job = Job(new_job_id(), request, self._settings)
        self._jobs[job.status.job_id] = job
        logger.info("Job %s créé (%d profils, %d avatars/profil)",
                    job.status.job_id, request.profile_count, request.avatars_per_profile)
        self._tasks[job.status.job_id] = asyncio.create_task(self._run(job, source))
        return job

    def resume(self, job_id: str) -> Job:
        """Relance un job interrompu depuis son dernier point de contrôle.

        Les profils déjà générés et les avatars déjà écrits sur disque sont
        repris tels quels : seul le reste est redemandé au modèle.
        """
        job = self._jobs.get(job_id)
        if job is not None and job.status.stage not in (JobStage.DONE, JobStage.ERROR):
            return job

        if job is None:
            state_file = self._settings.temp_dir / job_id / "state.json"
            if not state_file.exists():
                raise KeyError(job_id)
            payload = json.loads(state_file.read_text(encoding="utf-8"))
            request = GenerationRequest(**payload["request"])
            job = Job(job_id, request, self._settings)
            self._jobs[job_id] = job
        else:
            job.status.error = None
            job.status.completed_stages = []
            job.status.stage = JobStage.QUEUED

        source = self._settings.uploads_dir / f"{job.request.upload_id}.xlsx"
        if not source.exists():
            raise FileNotFoundError(source)

        logger.info("Job %s repris depuis son point de contrôle", job_id)
        self._tasks[job_id] = asyncio.create_task(self._run(job, source))
        return job

    async def _run(self, job: Job, source: Path) -> None:
        try:
            await self._pipeline(job, source)
        except asyncio.CancelledError:
            job.fail("Génération annulée.")
            raise
        except Exception as exc:  # noqa: BLE001 — remonté tel quel au client
            job.fail(str(exc))
        finally:
            self._persist_history()

    async def _pipeline(self, job: Job, source: Path) -> None:
        settings = self._settings
        request = job.request
        reference = date.today()
        job.work_dir.mkdir(parents=True, exist_ok=True)

        job.enter(JobStage.ANALYSE, "Analyse du modèle Excel")
        schema: WorkbookSchema = await asyncio.to_thread(introspect, source)
        femme_specs = build_femme_specs(schema.femmes)
        agent_specs = build_agent_specs(schema.agents)
        job.status.messages.append(
            f"Modèle : {len(schema.femmes.columns)} colonnes détectées sur « {schema.femmes.name} »"
        )

        openai = OpenAIService(settings)
        generator = ProfileGenerator(openai, settings)
        cached_agents, cached_profiles = job.load_checkpoint()

        job.enter(JobStage.AGENTS, "Génération des agents")
        agent_count = request.resolved_agent_count()
        agents = cached_agents or await generator.generate_agents(
            request, agent_specs, agent_count
        )
        job.save_checkpoint(agents, cached_profiles)

        job.enter(JobStage.PROFILS, f"Génération de {request.profile_count} profils")
        job.status.profiles_done = len(cached_profiles)

        async def on_batch(done: list[Profile]) -> None:
            job.status.profiles_done = len(done)
            job.save_checkpoint(agents, done)
            job.publish()

        profiles = await generator.generate_profiles(
            request, schema, femme_specs, agents, reference,
            on_batch=on_batch, already_done=cached_profiles,
        )
        assign_agents(profiles, agents)
        job.status.profiles_done = len(profiles)
        job.save_checkpoint(agents, profiles)

        job.enter(JobStage.VALIDATION, "Validation des profils")
        validator = Validator(schema, femme_specs)

        job.enter(JobStage.AVATARS, f"Génération de {job.status.avatars_total} avatars")
        images = ImageGenerator(openai, settings)
        existing = {p.name for p in job.photos_dir.glob("*.png")} if job.photos_dir.exists() else set()

        async def on_image(done: int) -> None:
            job.status.avatars_done = done
            job.publish()

        photos: list[PhotoRow] = []
        failures: dict[str, str] = {}
        if request.avatars_per_profile:
            photos, failures = await images.generate_for_profiles(
                profiles, request.avatars_per_profile, job.photos_dir, reference,
                on_progress=on_image, existing=existing,
            )

        report: ValidationReport = validator.run(
            profiles=profiles, agents=agents, photos=photos, photos_dir=job.photos_dir,
            reference=reference, expected_per_profile=request.avatars_per_profile,
            image_failures=failures,
        )
        job.status.report = report

        job.enter(JobStage.EXCEL, "Remplissage du classeur")
        stamp = datetime.now().strftime("%Y-%m-%d")
        excel_name = f"palab_dossier_{stamp}_{job.status.job_id}.xlsx"
        excel_path = job.output_dir / excel_name
        writer = ExcelWriter(schema)
        await asyncio.to_thread(
            writer.write,
            source=source, destination=excel_path, profiles=profiles, agents=agents,
            photos=photos, femme_specs=femme_specs, agent_specs=agent_specs,
            reference=reference,
        )
        job.status.excel_filename = excel_name

        job.enter(JobStage.ZIP, "Création de l'archive")
        zip_path = job.output_dir / "palab_dossier_final.zip"
        await asyncio.to_thread(
            build_archive,
            job_id=job.status.job_id, excel_path=excel_path, photos_dir=job.photos_dir,
            report=report, destination=zip_path,
        )
        job.status.zip_filename = zip_path.name

        job.enter(JobStage.DONE, "Dossier terminé")
        self._persist_history()
