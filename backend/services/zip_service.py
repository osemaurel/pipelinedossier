"""Assemblage de l'archive livrable."""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

from backend.core.logging import get_logger
from backend.models.schemas import ValidationReport

logger = get_logger(__name__)

README_TEMPLATE = """\
PALAB — DOSSIER DE DÉMONSTRATION
================================

Job          : {job_id}
Généré le    : {generated_at}
Contenu      : {profiles} profils, {agents} agents, {avatars} avatars

CE DOSSIER NE CONTIENT AUCUNE DONNÉE PERSONNELLE RÉELLE
-------------------------------------------------------
Les profils, les agences et les visuels de ce dossier sont entièrement
fabriqués par un générateur automatique. Ils ne décrivent aucune personne
réelle et ne doivent pas être présentés comme tels.

- Les adresses e-mail utilisent le domaine réservé `example.test` (RFC 6761)
  et ne peuvent pas recevoir de courrier.
- Les numéros de téléphone utilisent un indicatif non attribué.
- Les visuels du dossier `photos/` sont des illustrations de synthèse produites
  par IA. Ce ne sont pas des photographies, et leurs métadonnées PNG le
  mentionnent explicitement.

COLONNES DE VÉRIFICATION NON RENSEIGNÉES
----------------------------------------
Les colonnes « Type de pièce d'identité », « Numéro de pièce », « Contrat de
mandat signé », « Date de signature » et « Consentement publication photos »
portent la valeur « N/A — démonstration ».

Ces colonnes n'enregistrent pas une donnée mais le fait qu'un humain a vérifié
un document. Les renseigner automatiquement pour un personnage inexistant
produirait un dossier indiscernable d'un dossier réellement contrôlé. Le
« Lisez-moi » du modèle prévoit ce cas : un dossier incomplet reste importable
et demeure en attente côté administration. Le « Statut du dossier » est donc
positionné sur « À compléter ».

RAPPORT DE VALIDATION
---------------------
Voir `rapport_validation.txt`.
"""


def build_archive(
    *,
    job_id: str,
    excel_path: Path,
    photos_dir: Path,
    report: ValidationReport,
    destination: Path,
) -> Path:
    """Écrit `palab_dossier_final.zip` : Excel + photos + README + rapport."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    root = destination.stem
    readme = README_TEMPLATE.format(
        job_id=job_id,
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
        profiles=report.profiles,
        agents=report.agents,
        avatars=report.avatars,
    )

    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(excel_path, f"{root}/{excel_path.name}")
        if photos_dir.exists():
            for image in sorted(photos_dir.glob("*.png")):
                archive.write(image, f"{root}/photos/{image.name}")
        archive.writestr(f"{root}/README.txt", readme)
        archive.writestr(f"{root}/rapport_validation.txt", report.as_text())

    logger.info("ZIP généré : %s", destination.name)
    return destination
