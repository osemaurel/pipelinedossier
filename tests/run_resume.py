"""Vérifie qu'un job interrompu reprend à son point de contrôle.

On fabrique l'état d'un job tombé en panne à 60 % (6 profils sur 10, avatars
partiels), on le reprend, puis on contrôle que le travail déjà fait a bien été
conservé et non régénéré.

Usage : python -m tests.run_resume
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from backend.config import get_settings
from backend.core.logging import configure_logging
from backend.models.schemas import GenerationRequest, JobStage
from backend.services.job_manager import Job, JobManager


async def main() -> int:
    configure_logging()
    settings = get_settings()
    manager = JobManager(settings)

    upload_id = "resume"
    (settings.uploads_dir / f"{upload_id}.xlsx").write_bytes(
        Path("palabdossiercollecte.xlsx").read_bytes()
    )
    request = GenerationRequest(
        upload_id=upload_id, profile_count=10, agent_count=2, avatars_per_profile=2,
        countries=["Bénin", "Sénégal"], age_min=25, age_max=45,
    )

    # 1. Premier passage complet, pour disposer de données réalistes.
    seed = manager.start(request, settings.uploads_dir / f"{upload_id}.xlsx")
    while seed.status.stage not in (JobStage.DONE, JobStage.ERROR):
        await asyncio.sleep(0.3)
    if seed.status.stage is JobStage.ERROR:
        print("Échec du passage initial :", seed.status.error)
        return 1

    state = json.loads((seed.work_dir / "state.json").read_text(encoding="utf-8"))
    kept = state["profiles"][:6]
    kept_codes = [p["code_femme"] for p in kept]
    kept_names = [p["nom_legal_complet"] for p in kept]

    # 2. On rejoue un job « tombé en panne » à 6 profils sur 10.
    job_id = "JOB-20260810-CRASH"
    crashed = Job(job_id, request, settings)
    crashed.work_dir.mkdir(parents=True, exist_ok=True)
    (crashed.work_dir / "state.json").write_text(
        json.dumps({"job_id": job_id, "request": request.model_dump(),
                    "agents": state["agents"], "profiles": kept}, ensure_ascii=False),
        encoding="utf-8",
    )
    # Trois avatars déjà écrits : ils ne doivent pas être redemandés.
    crashed.photos_dir.mkdir(parents=True, exist_ok=True)
    preserved = sorted(seed.photos_dir.glob("*.png"))[:3]
    for image in preserved:
        (crashed.photos_dir / image.name).write_bytes(image.read_bytes())
    reused_bytes = {p.name: (crashed.photos_dir / p.name).read_bytes() for p in preserved}

    print(f"\n=== REPRISE : {len(kept)}/10 profils, {len(preserved)} avatars déjà présents ===")
    resumed = manager.resume(job_id)
    while resumed.status.stage not in (JobStage.DONE, JobStage.ERROR):
        await asyncio.sleep(0.3)

    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        print(f"{'✓' if condition else '✗'} {label}{(' — ' + detail) if detail else ''}")
        if not condition:
            failures.append(label)

    print()
    check("reprise terminée", resumed.status.stage is JobStage.DONE, resumed.status.error or "")
    final = json.loads((resumed.work_dir / "state.json").read_text(encoding="utf-8"))
    check("total de profils atteint", len(final["profiles"]) == 10,
          f"{len(final['profiles'])} profils")
    check("les 6 profils du point de contrôle sont conservés à l'identique",
          [p["code_femme"] for p in final["profiles"][:6]] == kept_codes
          and [p["nom_legal_complet"] for p in final["profiles"][:6]] == kept_names)
    check("les 4 profils manquants ont été générés",
          [p["code_femme"] for p in final["profiles"][6:]]
          == [f"PAL-{i:04d}" for i in range(7, 11)])
    check("aucun code dupliqué après reprise",
          len({p["code_femme"] for p in final["profiles"]}) == 10)
    check("les avatars déjà présents n'ont pas été régénérés",
          all((crashed.photos_dir / name).read_bytes() == blob
              for name, blob in reused_bytes.items()))
    check("tous les avatars attendus sont présents",
          len(list(crashed.photos_dir.glob("*.png"))) == 20,
          f"{len(list(crashed.photos_dir.glob('*.png')))} fichiers")
    check("dossier final produit",
          bool(resumed.status.excel_filename and resumed.status.zip_filename))
    report = resumed.status.report
    check("rapport sans erreur", bool(report and not report.errors),
          report.as_text().splitlines()[0] if report else "")

    print(f"\n{'REPRISE CONFORME' if not failures else f'{len(failures)} ÉCHEC(S)'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
