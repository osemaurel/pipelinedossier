"""Génération des agents et des profils, par lots, en sortie structurée.

Le schéma JSON imposé au modèle est construit à partir des colonnes réellement
présentes dans le classeur : listes déroulantes converties en `enum`, bornes de
longueur reprises des formules de contrôle. Rien n'est codé en dur.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from datetime import date, timedelta
from typing import Any, Awaitable, Callable

from backend.config import Settings
from backend.core.logging import get_logger
from backend.models.schemas import Agent, GenerationRequest, Profile
from backend.prompts.profile_prompt import (
    AGENT_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    ProfileBatchContext,
    build_agent_prompt,
    build_length_fix_prompt,
    build_profile_prompt,
)
from backend.services.excel_introspect import WorkbookSchema
from backend.services.field_policy import FieldSpec, FillMode, generated_specs
from backend.services.openai_service import OpenAIService

logger = get_logger(__name__)

INTEGER_FIELDS = {"taille_cm", "poids_kg", "age_recherche_min", "age_recherche_max"}
TEXT_FIELDS = ("accroche", "presentation", "recherche")
MAX_LENGTH_REPAIRS = 2


def _json_type(name: str) -> str:
    return "integer" if name in INTEGER_FIELDS else "string"


def _describe(spec: FieldSpec) -> str:
    column = spec.column
    parts = [column.header]
    if column.min_length and column.max_length:
        parts.append(f"entre {column.min_length} et {column.max_length} caractères")
    elif column.max_length:
        parts.append(f"{column.max_length} caractères maximum")
    if column.max_items:
        parts.append(f"{column.max_items} éléments maximum séparés par « ; »")
    return " — ".join(parts)


def allowed_for(spec: FieldSpec, filters: dict[str, list[str]] | None) -> list[str]:
    """Liste du modèle, éventuellement restreinte par les options avancées.

    Un filtre ne peut que réduire : une valeur absente du modèle est ignorée,
    sans quoi le classeur refuserait la saisie.
    """
    allowed = spec.column.allowed_values
    chosen = (filters or {}).get(spec.name)
    if not allowed or not chosen:
        return allowed
    narrowed = [value for value in allowed if value in set(chosen)]
    return narrowed or allowed


def build_json_schema(
    specs: list[FieldSpec], root_key: str, filters: dict[str, list[str]] | None = None
) -> dict[str, Any]:
    """Schéma strict : toutes les propriétés requises, aucune propriété libre."""
    properties: dict[str, Any] = {}
    for spec in generated_specs(specs):
        entry: dict[str, Any] = {
            "type": _json_type(spec.name),
            "description": _describe(spec),
        }
        values = allowed_for(spec, filters)
        if values:
            entry["enum"] = values
        properties[spec.name] = entry

    item_schema = {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {root_key: {"type": "array", "items": item_schema}},
        "required": [root_key],
        "additionalProperties": False,
    }


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", ".", _strip_accents(text).lower()).strip(".")
    return cleaned or "contact"


def demo_email(*parts: str) -> str:
    """Adresse de démonstration en domaine réservé (RFC 6761 : `.test`)."""
    return f"{'.'.join(_slug(p) for p in parts if p)}@example.test"


def demo_phone(index: int) -> str:
    """Numéro de démonstration dans la plage réservée à la fiction (+99)."""
    return f"+99 00 {index // 100 % 100:02d} {index % 100:02d} 00"


def birth_window(age_min: int, age_max: int, reference: date) -> tuple[date, date]:
    """Fenêtre de naissance donnant un âge dans [age_min, age_max] à la référence."""
    youngest = reference - timedelta(days=int(age_min * 365.2425))
    oldest = reference - timedelta(days=int((age_max + 1) * 365.2425) - 1)
    return oldest, youngest


def sentence_safe_trim(text: str, limit: int) -> str:
    """Coupe sur une frontière de phrase, jamais au milieu d'une idée."""
    if len(text) <= limit:
        return text
    window = text[: limit + 1]
    for separator in (". ", " ! ", " ? ", "… ", "; "):
        cut = window.rfind(separator)
        if cut > limit * 0.5:
            return text[: cut + 1].strip()
    cut = window.rfind(" ")
    return (text[:cut] if cut > 0 else text[:limit]).rstrip(" ,;:") + "."


class ProfileGenerator:
    def __init__(self, openai: OpenAIService, settings: Settings) -> None:
        self._openai = openai
        self._settings = settings

    async def generate_agents(
        self, request: GenerationRequest, specs: list[FieldSpec], count: int
    ) -> list[Agent]:
        codes = [f"AG-{index:02d}" for index in range(1, count + 1)]
        schema = build_json_schema(specs, "agents")
        payload = await self._openai.structured_json(
            system_prompt=AGENT_SYSTEM_PROMPT,
            user_prompt=build_agent_prompt(count, request.countries, codes),
            schema_name="agents",
            json_schema=schema,
            temperature=0.8,
        )
        raw = payload.get("agents", [])[:count]
        agents: list[Agent] = []
        for index, item in enumerate(raw):
            code = codes[index]
            nom = str(item.get("nom_agence") or f"Agence {code}")
            agents.append(
                Agent(
                    code_agent=code,
                    nom_agence=nom,
                    personne_responsable=str(item.get("personne_responsable") or "Mme A. Fictive"),
                    pays=str(item.get("pays") or request.countries[index % len(request.countries)]),
                    ville=str(item.get("ville") or ""),
                    langues=str(item.get("langues") or "Français"),
                    email=demo_email(nom, code),
                    telephone=demo_phone(index + 1),
                )
            )
        # Complète si le modèle en a renvoyé moins que demandé.
        for index in range(len(agents), count):
            code = codes[index]
            agents.append(
                Agent(
                    code_agent=code,
                    nom_agence=f"Agence {code}",
                    personne_responsable="Mme A. Fictive",
                    pays=request.countries[index % len(request.countries)],
                    ville="",
                    langues="Français",
                    email=demo_email(f"agence{code}"),
                    telephone=demo_phone(index + 1),
                )
            )
        logger.info("%d agents générés : %s", len(agents), ", ".join(a.code_agent for a in agents))
        return agents

    async def generate_profiles(
        self,
        request: GenerationRequest,
        schema: WorkbookSchema,
        specs: list[FieldSpec],
        agents: list[Agent],
        reference: date,
        on_batch: Callable[[list[Profile]], Awaitable[None]] | None = None,
        already_done: list[Profile] | None = None,
    ) -> list[Profile]:
        profiles: list[Profile] = list(already_done or [])
        filters = request.field_filters
        json_schema = build_json_schema(specs, "profils", filters)
        enum_values = {
            spec.name: allowed_for(spec, filters)
            for spec in generated_specs(specs)
            if spec.column.allowed_values
        }
        length_rules = {
            spec.name: (spec.column.min_length, spec.column.max_length)
            for spec in generated_specs(specs)
            if spec.column.max_length
        }
        interests = next(
            (s.column.max_items for s in generated_specs(specs) if s.name == "centres_interet"),
            None,
        )
        oldest, youngest = birth_window(request.age_min, request.age_max, reference)
        batch_size = max(1, self._settings.profile_batch_size)
        batch_index = len(profiles) // batch_size

        while len(profiles) < request.profile_count:
            remaining = request.profile_count - len(profiles)
            size = min(batch_size, remaining)
            batch_index += 1
            context = ProfileBatchContext(
                count=size,
                countries=request.countries,
                cities=request.cities,
                professions=request.professions,
                birth_window=(oldest.isoformat(), youngest.isoformat()),
                age_range=(request.age_min, request.age_max),
                agent_codes=[agent.code_agent for agent in agents],
                used_first_names=[p.prenom_affiche for p in profiles][-60:],
                enum_values=enum_values,
                length_rules=length_rules,
                max_interests=interests,
                reference_date=reference.isoformat(),
                batch_index=batch_index,
            )
            payload = await self._openai.structured_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=build_profile_prompt(context),
                schema_name="profils",
                json_schema=json_schema,
            )
            items = payload.get("profils", [])[:size]
            if not items:
                raise RuntimeError("Le modèle n'a renvoyé aucun profil pour ce lot.")

            batch: list[Profile] = []
            for offset, item in enumerate(items):
                index = len(profiles) + offset + 1
                profile = self._materialise(item, index, agents, oldest, youngest, reference)
                batch.append(profile)

            await self._enforce_lengths(batch, length_rules)
            profiles.extend(batch)
            logger.info(
                "Profils %d-%d terminés (%d/%d)",
                len(profiles) - len(batch) + 1, len(profiles),
                len(profiles), request.profile_count,
            )
            if on_batch:
                await on_batch(profiles)

        return profiles[: request.profile_count]

    def _materialise(
        self,
        item: dict[str, Any],
        index: int,
        agents: list[Agent],
        oldest: date,
        youngest: date,
        reference: date,
    ) -> Profile:
        data = dict(item)
        data["code_femme"] = f"PAL-{index:04d}"
        data["code_agent"] = agents[(index - 1) % len(agents)].code_agent

        for field in INTEGER_FIELDS:
            try:
                data[field] = int(float(data.get(field, 0)))
            except (TypeError, ValueError):
                data[field] = 0

        profile = Profile(**data)
        profile.email = demo_email(profile.prenom_affiche, profile.code_femme)
        profile.telephone = demo_phone(index)
        return self._enforce_coherence(profile, oldest, youngest, reference)

    def _enforce_coherence(
        self, profile: Profile, oldest: date, youngest: date, reference: date
    ) -> Profile:
        """Corrections déterministes que le backend ne délègue pas au modèle."""
        age = profile.age_at(reference)
        if age is None or not (oldest <= _safe_date(profile.date_naissance, youngest) <= youngest):
            span = (youngest - oldest).days or 1
            profile.date_naissance = (oldest + timedelta(days=(hash(profile.code_femme) % span))).isoformat()
            age = profile.age_at(reference)

        if not profile.prenom_affiche:
            profile.prenom_affiche = profile.nom_legal_complet.split(" ")[0]
        if not profile.ville_affichee:
            profile.ville_affichee = profile.ville_residence
        if not profile.pays_affiche:
            profile.pays_affiche = profile.pays_residence

        if profile.age_recherche_min >= profile.age_recherche_max:
            profile.age_recherche_min = max(18, (age or 30) - 5)
            profile.age_recherche_max = profile.age_recherche_min + 15
        return profile

    async def _enforce_lengths(
        self, batch: list[Profile], rules: dict[str, tuple[int | None, int | None]]
    ) -> None:
        """Vérifie les longueurs côté backend et fait réécrire ce qui dépasse."""
        tasks = [
            self._fix_field(profile, field, low, high)
            for profile in batch
            for field, (low, high) in rules.items()
            if high and field in TEXT_FIELDS
        ]
        await asyncio.gather(*tasks)

    async def _fix_field(
        self, profile: Profile, field: str, low: int | None, high: int
    ) -> None:
        for _ in range(MAX_LENGTH_REPAIRS):
            text = str(getattr(profile, field, ""))
            if (low is None or len(text) >= low) and len(text) <= high:
                return
            logger.info(
                "%s : %s fait %d caractères (attendu %s-%s), réécriture.",
                profile.code_femme, field, len(text), low, high,
            )
            rewritten = await self._openai.plain_text(
                system_prompt="Tu réécris des textes de profil en respectant une longueur imposée.",
                user_prompt=build_length_fix_prompt(field, text, low, high),
            )
            if rewritten:
                setattr(profile, field, rewritten.strip().strip('"'))

        # Dernier recours : coupe propre, sur une frontière de phrase.
        text = str(getattr(profile, field, ""))
        if len(text) > high:
            setattr(profile, field, sentence_safe_trim(text, high))


def _safe_date(value: str, fallback: date) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return fallback


def assign_agents(profiles: list[Profile], agents: list[Agent]) -> None:
    """Répartition circulaire, garantissant que chaque code agent existe."""
    if not agents:
        return
    for index, profile in enumerate(profiles):
        profile.code_agent = agents[index % len(agents)].code_agent
