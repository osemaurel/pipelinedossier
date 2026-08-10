"""Modèles Pydantic : requêtes API, enregistrements produits, rapports."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class JobStage(str, Enum):
    QUEUED = "queued"
    ANALYSE = "analyse"
    AGENTS = "agents"
    PROFILS = "profils"
    VALIDATION = "validation"
    AVATARS = "avatars"
    EXCEL = "excel"
    ZIP = "zip"
    DONE = "done"
    ERROR = "error"


STAGE_LABELS: dict[JobStage, str] = {
    JobStage.QUEUED: "En attente",
    JobStage.ANALYSE: "Analyse du fichier Excel",
    JobStage.AGENTS: "Génération des agents",
    JobStage.PROFILS: "Génération des profils",
    JobStage.VALIDATION: "Validation des profils",
    JobStage.AVATARS: "Génération des avatars",
    JobStage.EXCEL: "Remplissage Excel",
    JobStage.ZIP: "Création du ZIP",
    JobStage.DONE: "Terminé",
    JobStage.ERROR: "Erreur",
}


class GenerationRequest(BaseModel):
    upload_id: str
    profile_count: int = Field(default=3, ge=1, le=500)
    agent_count: int | None = Field(default=None, ge=1, le=100)
    avatars_per_profile: int = Field(default=3, ge=0, le=10)
    countries: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    professions: list[str] = Field(default_factory=list)
    age_min: int = Field(default=25, ge=18, le=99)
    age_max: int = Field(default=45, ge=18, le=99)
    # Options avancées : restreint une liste du modèle à un sous-ensemble choisi.
    # Clé = nom canonique du champ (situation, niveau_etudes, type_relation…).
    field_filters: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_ages(self) -> GenerationRequest:
        if self.age_min > self.age_max:
            raise ValueError("L'âge minimum ne peut pas dépasser l'âge maximum.")
        if not self.countries:
            raise ValueError("Sélectionnez au moins un pays.")
        return self

    @field_validator("countries", "cities", "professions", mode="before")
    @classmethod
    def clean_list(cls, value: Any) -> list[str]:
        if not value:
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def resolved_agent_count(self) -> int:
        """Nombre d'agents demandé, ou une répartition automatique ~10 profils/agent."""
        if self.agent_count:
            return min(self.agent_count, self.profile_count)
        return max(1, min(self.profile_count, round(self.profile_count / 10) or 1))


class Agent(BaseModel):
    code_agent: str
    nom_agence: str
    personne_responsable: str
    pays: str
    ville: str
    langues: str
    email: str = ""
    telephone: str = ""


class Profile(BaseModel):
    code_femme: str = ""
    code_agent: str = ""
    nom_legal_complet: str
    date_naissance: str
    nationalite: str
    pays_residence: str
    ville_residence: str
    prenom_affiche: str
    ville_affichee: str
    pays_affiche: str
    langues: str
    situation: str
    enfants: str
    profession: str
    niveau_etudes: str
    taille_cm: int
    poids_kg: int
    yeux: str
    cheveux: str
    religion: str
    tabac: str
    alcool: str
    centres_interet: str
    type_relation: str
    age_recherche_min: int
    age_recherche_max: int
    prete_a_demenager: str
    accroche: str
    presentation: str
    recherche: str
    email: str = ""
    telephone: str = ""

    def age_at(self, reference: date) -> int | None:
        try:
            born = datetime.strptime(self.date_naissance, "%Y-%m-%d").date()
        except ValueError:
            return None
        return (
            reference.year
            - born.year
            - ((reference.month, reference.day) < (born.month, born.day))
        )


class PhotoRow(BaseModel):
    code_femme: str
    filename: str
    order: int
    caption: str
    notes: str


class ValidationIssue(BaseModel):
    severity: str  # "erreur" | "avertissement"
    scope: str
    message: str


class ValidationReport(BaseModel):
    checks: list[str] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    profiles: int = 0
    agents: int = 0
    avatars: int = 0

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "erreur"]

    def as_text(self) -> str:
        lines = list(self.checks)
        for issue in self.issues:
            prefix = "✗" if issue.severity == "erreur" else "!"
            lines.append(f"{prefix} [{issue.scope}] {issue.message}")
        return "\n".join(lines)


class JobStatus(BaseModel):
    job_id: str
    stage: JobStage
    stage_label: str
    created_at: datetime
    updated_at: datetime
    profiles_done: int = 0
    profiles_total: int = 0
    avatars_done: int = 0
    avatars_total: int = 0
    completed_stages: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    error: str | None = None
    excel_filename: str | None = None
    zip_filename: str | None = None
    report: ValidationReport | None = None
    request: GenerationRequest | None = None

    @property
    def progress(self) -> float:
        weights = {
            JobStage.QUEUED: 0.0, JobStage.ANALYSE: 0.03, JobStage.AGENTS: 0.08,
            JobStage.PROFILS: 0.10, JobStage.VALIDATION: 0.55, JobStage.AVATARS: 0.60,
            JobStage.EXCEL: 0.92, JobStage.ZIP: 0.96, JobStage.DONE: 1.0,
            JobStage.ERROR: 1.0,
        }
        base = weights.get(self.stage, 0.0)
        if self.stage is JobStage.PROFILS and self.profiles_total:
            return base + 0.45 * (self.profiles_done / self.profiles_total)
        if self.stage is JobStage.AVATARS and self.avatars_total:
            return base + 0.32 * (self.avatars_done / self.avatars_total)
        return base


class HistoryEntry(BaseModel):
    job_id: str
    created_at: datetime
    stage: JobStage
    profiles: int
    agents: int
    avatars: int
    excel_filename: str | None
    zip_filename: str | None
