"""Prompts de génération des avatars.

Les visuels produits sont des avatars de synthèse assumés comme tels. Le modèle
Excel réclame des photographies de personnes réelles ; un générateur ne peut pas
les fournir, et fabriquer des images destinées à passer pour des photographies
authentiques d'une personne inventée serait précisément l'usage à écarter. On
génère donc des portraits illustrés, stylisés et lisibles comme synthétiques.
"""

from __future__ import annotations

from dataclasses import dataclass

# Variantes de cadrage : la cohérence du personnage vient de la description
# partagée, la variété vient de ces angles.
AVATAR_VARIANTS: list[str] = [
    "portrait de face, cadrage buste, regard vers l'objectif, sourire discret",
    "portrait de trois quarts, cadrage épaules, regard légèrement de côté, expression calme",
    "portrait en pied ou cadrage taille, posture détendue, expression naturelle",
    "portrait rapproché sur le visage, lumière douce, expression pensive",
    "portrait de trois quarts opposé, cadrage buste, sourire franc",
]

STYLE_DIRECTIVE = (
    "Illustration numérique de portrait, style vectoriel éditorial contemporain : "
    "aplats de couleur, ombrage doux, traits nets, arrière-plan uni ou très simplifié. "
    "Rendu clairement illustré et non photographique — ce doit être lisible au premier "
    "coup d'œil comme un avatar de synthèse, jamais comme une photographie. "
    "Pas de texte, pas de logo, pas de filigrane. Cadre vertical."
)


@dataclass(slots=True)
class AvatarContext:
    code_femme: str
    age: int
    ville: str
    pays: str
    profession: str
    yeux: str
    cheveux: str
    variant_index: int


def build_character_sheet(context: AvatarContext) -> str:
    """Description stable du personnage, partagée par toutes ses variantes."""
    return (
        f"Femme adulte fictive d'environ {context.age} ans, "
        f"yeux {context.yeux.lower()}, cheveux {context.cheveux.lower()}, "
        f"exerçant comme {context.profession.lower()} à {context.ville} ({context.pays}). "
        "Tenue de ville sobre et couvrante."
    )


def build_avatar_prompt(context: AvatarContext) -> str:
    variant = AVATAR_VARIANTS[context.variant_index % len(AVATAR_VARIANTS)]
    return (
        f"{STYLE_DIRECTIVE}\n\n"
        f"Personnage (identique sur toutes les variantes) : {build_character_sheet(context)}\n\n"
        f"Variante demandée : {variant}.\n\n"
        "Le personnage est un avatar imaginaire. Ne reproduis les traits d'aucune "
        "personne réelle ou célèbre. Portrait décent, non suggestif."
    )
