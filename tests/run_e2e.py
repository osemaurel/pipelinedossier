"""Exécution de bout en bout du pipeline, contre le serveur OpenAI simulé.

Usage : python -m tests.run_e2e [nombre_de_profils] [avatars_par_profil]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from backend.config import get_settings
from backend.core.logging import configure_logging
from backend.models.schemas import GenerationRequest, JobStage
from backend.services.job_manager import JobManager


async def main() -> int:
    configure_logging()
    settings = get_settings()
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    avatars = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    source = Path("palabdossiercollecte.xlsx")
    upload_id = "e2e"
    (settings.uploads_dir / f"{upload_id}.xlsx").write_bytes(source.read_bytes())

    manager = JobManager(settings)
    request = GenerationRequest(
        upload_id=upload_id,
        profile_count=count,
        agent_count=max(1, count // 10) or 1,
        avatars_per_profile=avatars,
        countries=["Bénin", "Côte d'Ivoire", "Sénégal", "Togo", "Cameroun", "Maroc"],
        age_min=25,
        age_max=45,
    )
    job = manager.start(request, settings.uploads_dir / f"{upload_id}.xlsx")

    while job.status.stage not in (JobStage.DONE, JobStage.ERROR):
        await asyncio.sleep(0.4)

    print("\n=== RÉSULTAT ===")
    print("Job      :", job.status.job_id)
    print("Étape    :", job.status.stage.value)
    if job.status.error:
        print("Erreur   :", job.status.error)
        return 1
    print("Excel    :", job.status.excel_filename)
    print("ZIP      :", job.status.zip_filename)
    print("\n=== RAPPORT DE VALIDATION ===")
    print(job.status.report.as_text() if job.status.report else "(aucun)")
    print("\nSortie   :", job.output_dir)
    return 0 if job.status.report and not job.status.report.errors else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
