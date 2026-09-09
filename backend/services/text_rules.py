"""Règles de contenu sur les textes de profil.

Une consigne dans un prompt n'est pas une garantie : le modèle en écarte
régulièrement une sur plusieurs dizaines de profils. Ces règles se vérifient
donc côté serveur, et alimentent la réécriture comme le rapport de validation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from backend.models.schemas import Profile

# « 40 ans », « quarante ans », « la quarantaine », « 35-50 ans ».
_AGE_DIGITS = re.compile(r"\b\d{2}\s*(?:a|à|-)?\s*\d{0,2}\s*ans?\b", re.IGNORECASE)
_AGE_WORDS = re.compile(
    r"\b(?:trentaine|quarantaine|cinquantaine|soixantaine|vingtaine)\b", re.IGNORECASE
)
_AGE_SPELLED = re.compile(
    r"\b(?:vingt|trente|quarante|cinquante|soixante)(?:[- ](?:et[- ])?\w+)?\s+ans\b",
    re.IGNORECASE,
)

RULE_PRESENTATION = (
    "la présentation ne doit jamais nommer la ville ni le pays où elle vit, "
    "ni y faire allusion"
)
RULE_RECHERCHE = (
    "le texte « ce que je recherche » ne doit mentionner aucun âge, ni en chiffres, "
    "ni en toutes lettres, ni par une tranche"
)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _places(profile: Profile) -> list[str]:
    """Lieux à ne pas retrouver dans la présentation."""
    candidates = (
        profile.ville_residence,
        profile.ville_affichee,
        profile.pays_residence,
        profile.pays_affiche,
    )
    return [place.strip() for place in candidates if place and len(place.strip()) > 2]


def presentation_mentions_place(profile: Profile) -> str | None:
    """Renvoie le lieu trouvé dans la présentation, sinon None."""
    haystack = _fold(profile.presentation)
    for place in _places(profile):
        needle = _fold(place)
        if re.search(rf"\b{re.escape(needle)}\b", haystack):
            return place
    return None


def recherche_mentions_age(profile: Profile) -> str | None:
    """Renvoie l'extrait fautif du texte de recherche, sinon None."""
    text = profile.recherche
    for pattern in (_AGE_DIGITS, _AGE_SPELLED, _AGE_WORDS):
        found = pattern.search(text)
        if found:
            return found.group(0)
    return None


@dataclass(slots=True)
class Violation:
    field: str
    rule: str
    excerpt: str


def find_violations(profile: Profile) -> list[Violation]:
    found: list[Violation] = []
    place = presentation_mentions_place(profile)
    if place:
        found.append(Violation("presentation", RULE_PRESENTATION, place))
    age = recherche_mentions_age(profile)
    if age:
        found.append(Violation("recherche", RULE_RECHERCHE, age))
    return found
