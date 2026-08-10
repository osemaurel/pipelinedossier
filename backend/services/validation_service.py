"""Validation du dossier avant export.

Les règles ne sont pas inventées : elles sont relues depuis le modèle
(listes déroulantes, bornes des formules de contrôle) puis confrontées aux
données produites et aux fichiers réellement présents sur le disque.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from backend.core.logging import get_logger
from backend.models.schemas import (
    Agent,
    PhotoRow,
    Profile,
    ValidationIssue,
    ValidationReport,
)
from backend.services.excel_introspect import WorkbookSchema
from backend.services.field_policy import FieldSpec, FillMode, generated_specs

logger = get_logger(__name__)

CODE_FEMME = re.compile(r"^PAL-\d{4}$")
CODE_AGENT = re.compile(r"^AG-\d{2}$")
FILENAME = re.compile(r"^PAL-\d{4}_avatar_\d{2}\.png$")


class Validator:
    def __init__(self, schema: WorkbookSchema, specs: list[FieldSpec]) -> None:
        self._schema = schema
        self._specs = specs

    def run(
        self,
        *,
        profiles: list[Profile],
        agents: list[Agent],
        photos: list[PhotoRow],
        photos_dir: Path,
        reference: date,
        expected_per_profile: int,
        image_failures: dict[str, str],
    ) -> ValidationReport:
        report = ValidationReport(
            profiles=len(profiles), agents=len(agents), avatars=len(photos)
        )
        report.checks.append(f"✓ {len(profiles)} profils générés")
        report.checks.append(f"✓ {len(agents)} agents générés")
        report.checks.append(f"✓ {len(photos)} avatars générés")

        self._check_codes(profiles, agents, report)
        self._check_dates_and_ages(profiles, reference, report)
        self._check_allowed_values(profiles, report)
        self._check_text_lengths(profiles, report)
        self._check_completeness(profiles, report)
        self._check_photos(profiles, photos, photos_dir, expected_per_profile, report)

        for code, reason in image_failures.items():
            report.issues.append(
                ValidationIssue(
                    severity="avertissement", scope=code,
                    message=f"avatar(s) non générés : {reason}",
                )
            )
        return report

    def _check_codes(
        self, profiles: list[Profile], agents: list[Agent], report: ValidationReport
    ) -> None:
        codes = [p.code_femme for p in profiles]
        duplicates = {code for code in codes if codes.count(code) > 1}
        malformed = [code for code in codes if not CODE_FEMME.match(code)]
        agent_codes = {a.code_agent for a in agents}
        agent_dupes = len(agent_codes) != len(agents)
        orphans = sorted({p.code_femme for p in profiles if p.code_agent not in agent_codes})
        bad_agents = [a.code_agent for a in agents if not CODE_AGENT.match(a.code_agent)]

        if duplicates:
            report.issues.append(ValidationIssue(
                severity="erreur", scope="codes",
                message=f"codes femme dupliqués : {', '.join(sorted(duplicates))}"))
        else:
            report.checks.append(f"✓ {len(set(codes))} codes uniques")
            report.checks.append("✓ 0 doublon")

        if malformed:
            report.issues.append(ValidationIssue(
                severity="erreur", scope="codes",
                message=f"format de code femme invalide : {', '.join(malformed[:5])}"))
        if bad_agents:
            report.issues.append(ValidationIssue(
                severity="erreur", scope="codes",
                message=f"format de code agent invalide : {', '.join(bad_agents[:5])}"))
        if agent_dupes:
            report.issues.append(ValidationIssue(
                severity="erreur", scope="agents", message="codes agent dupliqués"))
        if orphans:
            report.issues.append(ValidationIssue(
                severity="erreur", scope="agents",
                message=f"profils rattachés à un agent inexistant : {', '.join(orphans[:5])}"))
        else:
            report.checks.append("✓ tous les codes agent référencés existent")

    def _check_dates_and_ages(
        self, profiles: list[Profile], reference: date, report: ValidationReport
    ) -> None:
        invalid = [p.code_femme for p in profiles if p.age_at(reference) is None]
        if invalid:
            report.issues.append(ValidationIssue(
                severity="erreur", scope="dates",
                message=f"date de naissance illisible : {', '.join(invalid[:5])}"))
            return
        report.checks.append("✓ dates de naissance valides")

        incoherent = [
            p.code_femme for p in profiles
            if not (18 <= (p.age_at(reference) or 0) <= 99)
        ]
        if incoherent:
            report.issues.append(ValidationIssue(
                severity="erreur", scope="âges",
                message=f"âge hors bornes : {', '.join(incoherent[:5])}"))
        else:
            report.checks.append("✓ âges cohérents avec les dates de naissance")

        bad_range = [
            p.code_femme for p in profiles if p.age_recherche_min >= p.age_recherche_max
        ]
        if bad_range:
            report.issues.append(ValidationIssue(
                severity="avertissement", scope="âges",
                message=f"tranche recherchée incohérente : {', '.join(bad_range[:5])}"))

    def _check_allowed_values(self, profiles: list[Profile], report: ValidationReport) -> None:
        """Confronte chaque champ aux listes déroulantes réellement définies."""
        offenders: list[str] = []
        for spec in generated_specs(self._specs):
            allowed = spec.column.allowed_values
            if not allowed:
                continue
            allowed_set = set(allowed)
            for profile in profiles:
                value = str(getattr(profile, spec.name, "") or "")
                if value and value not in allowed_set:
                    offenders.append(f"{profile.code_femme}/{spec.name}={value!r}")
        if offenders:
            report.issues.append(ValidationIssue(
                severity="erreur", scope="listes",
                message=f"{len(offenders)} valeur(s) hors liste Excel : {', '.join(offenders[:5])}"))
        else:
            report.checks.append("✓ toutes les valeurs respectent les listes du modèle")

    def _check_text_lengths(self, profiles: list[Profile], report: ValidationReport) -> None:
        for spec in generated_specs(self._specs):
            high = spec.column.max_length
            if not high:
                continue
            low = spec.column.min_length
            too_long = [
                p.code_femme for p in profiles if len(str(getattr(p, spec.name, ""))) > high
            ]
            too_short = [
                p.code_femme for p in profiles
                if low and len(str(getattr(p, spec.name, ""))) < low
            ]
            label = spec.column.header.split("(")[0].strip().lower()
            if too_long:
                report.issues.append(ValidationIssue(
                    severity="erreur", scope="textes",
                    message=f"{len(too_long)} {label} trop longue(s) : {', '.join(too_long[:5])}"))
            else:
                report.checks.append(f"✓ 0 {label} trop longue")
            if too_short:
                report.issues.append(ValidationIssue(
                    severity="avertissement", scope="textes",
                    message=f"{len(too_short)} {label} sous le minimum du modèle "
                            f"({low}) : {', '.join(too_short[:5])}"))

    def _check_completeness(self, profiles: list[Profile], report: ValidationReport) -> None:
        incomplete: list[str] = []
        for profile in profiles:
            for spec in generated_specs(self._specs):
                value = getattr(profile, spec.name, None)
                if value is None or (isinstance(value, str) and not value.strip()):
                    incomplete.append(profile.code_femme)
                    break
        if incomplete:
            report.issues.append(ValidationIssue(
                severity="erreur", scope="profils",
                message=f"{len(incomplete)} profil(s) incomplet(s) : {', '.join(incomplete[:5])}"))
        else:
            report.checks.append("✓ 0 profil incomplet")

    def _check_photos(
        self,
        profiles: list[Profile],
        photos: list[PhotoRow],
        photos_dir: Path,
        expected_per_profile: int,
        report: ValidationReport,
    ) -> None:
        if expected_per_profile == 0:
            report.checks.append("✓ génération d'avatars désactivée")
            return

        codes = {p.code_femme for p in profiles}
        bad_names = [row.filename for row in photos if not FILENAME.match(row.filename)]
        orphan_rows = [row.filename for row in photos if row.code_femme not in codes]
        on_disk = {path.name for path in photos_dir.glob("*.png")} if photos_dir.exists() else set()
        referenced = {row.filename for row in photos}
        missing = sorted(referenced - on_disk)
        extra = sorted(on_disk - referenced)

        if bad_names:
            report.issues.append(ValidationIssue(
                severity="erreur", scope="photos",
                message=f"nom de fichier non conforme : {', '.join(bad_names[:5])}"))
        else:
            report.checks.append("✓ noms de fichiers conformes")

        if orphan_rows:
            report.issues.append(ValidationIssue(
                severity="erreur", scope="photos",
                message=f"lignes Photos sans profil correspondant : {', '.join(orphan_rows[:5])}"))

        if missing:
            report.issues.append(ValidationIssue(
                severity="erreur", scope="photos",
                message=f"{len(missing)} fichier(s) référencés dans Excel mais absents du disque : "
                        f"{', '.join(missing[:5])}"))
        else:
            report.checks.append(f"✓ {len(referenced)} fichiers image présents")

        if extra:
            report.issues.append(ValidationIssue(
                severity="avertissement", scope="photos",
                message=f"{len(extra)} fichier(s) présents mais non référencés : "
                        f"{', '.join(extra[:5])}"))

        short = [
            code for code in sorted(codes)
            if sum(1 for row in photos if row.code_femme == code) < expected_per_profile
        ]
        if short:
            report.issues.append(ValidationIssue(
                severity="avertissement", scope="photos",
                message=f"{len(short)} profil(s) sous le quota de {expected_per_profile} avatars : "
                        f"{', '.join(short[:5])}"))
        else:
            report.checks.append(f"✓ {expected_per_profile} avatars par profil")
