"""Prompts de génération des avatars.

Chaque visuel est construit à partir des données réelles du profil : profession,
ville, centres d'intérêt. La cohérence du personnage vient d'une description
physique stable, partagée par toutes ses variantes ; la variété vient du décor,
de la tenue, de la lumière et du cadrage, qui changent à chaque prise.

Les consignes de cadrage et la liste de ce qui est à éviter sont reprises du
« Lisez-moi » du modèle, qui décrit précisément les photos attendues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AvatarStyle(str, Enum):
    """Rendu des visuels.

    `ILLUSTRATION` produit des portraits dessinés, lisibles au premier coup d'œil
    comme des avatars de synthèse. `PHOTO` produit des portraits photoréalistes :
    à réserver aux plateformes qui indiquent à leurs utilisateurs que les
    personnages sont générés, puisque rien dans l'image ne le signalera plus.
    """

    ILLUSTRATION = "illustration"
    PHOTO = "photo"


STYLE_DIRECTIVES: dict[AvatarStyle, str] = {
    AvatarStyle.ILLUSTRATION: (
        "Illustration numérique de portrait, style vectoriel éditorial contemporain : "
        "aplats de couleur, ombrage doux, traits nets. Rendu clairement illustré et "
        "non photographique."
    ),
    AvatarStyle.PHOTO: (
        "Photographie de portrait naturelle, objectif 50 mm, faible profondeur de champ, "
        "lumière naturelle, grain discret. Rendu réaliste et non retouché, sans effet "
        "de studio publicitaire."
    ),
}

# Repris du « Lisez-moi » : « À éviter — captures d'écran, filtres lourds, texte
# ou logo incrusté, photos de groupe en principale, images floues, nudité. »
NEGATIVE_DIRECTIVE = (
    "La personne est seule sur l'image. Pas de texte, pas de logo, pas de filigrane, "
    "pas de filtre marqué, image nette. Tenue décente et couvrante, cadrage non suggestif."
)

# Cadrage de la photo principale, imposé par le « Lisez-moi » du modèle :
# « Portrait vertical, visage net et bien éclairé, seule sur la photo. »
MAIN_SHOT = "portrait vertical serré sur le visage, regard vers l'objectif, expression avenante"

FRAMINGS: list[str] = [
    "cadrage buste, de trois quarts, regard vers l'objectif",
    "cadrage à mi-corps, posture détendue, regard légèrement de côté",
    "plan taille, debout, expression naturelle",
    "portrait rapproché, de trois quarts opposé, sourire discret",
    "plan large, la personne occupe le tiers de l'image, décor visible",
    "cadrage buste, assise, appuyée sur un accoudoir",
]

SETTINGS: list[str] = [
    "dans le salon d'un appartement, lumière douce entrant par la fenêtre",
    "à la terrasse d'un café, en fin d'après-midi",
    "dans une rue commerçante animée, arrière-plan flou",
    "sur un marché en plein air, étals colorés derrière elle",
    "dans un parc urbain, végétation en arrière-plan",
    "au bord de l'eau, ciel dégagé de fin de journée",
    "devant un mur coloré du centre-ville",
    "dans une cour intérieure ombragée",
    "sur un balcon donnant sur la ville",
    "dans un intérieur simple et lumineux, mur uni",
]

OUTFITS: list[str] = [
    "tenue de ville simple, chemisier et pantalon",
    "robe en tissu imprimé aux motifs colorés",
    "tenue traditionnelle en pagne, coupe moderne",
    "jean et haut uni, veste légère",
    "tenue soignée de sortie, coupe sobre",
    "haut en lin clair, foulard noué",
    "ensemble décontracté, gilet fin",
]

LIGHTS: list[str] = [
    "lumière naturelle du matin",
    "lumière chaude de fin de journée",
    "ciel légèrement couvert, lumière diffuse",
    "lumière d'intérieur douce",
    "contre-jour léger en fin d'après-midi",
]


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
    centres_interet: str = ""
    style: AvatarStyle = AvatarStyle.ILLUSTRATION
    seed: int = field(default=0)

    def __post_init__(self) -> None:
        # Décalage stable par personne : deux profils ne suivent pas la même
        # séquence de décors, mais un même profil reste reproductible.
        self.seed = sum(ord(c) for c in self.code_femme)


def build_character_sheet(context: AvatarContext) -> str:
    """Description physique stable, identique sur toutes les variantes."""
    return (
        f"Femme adulte fictive d'environ {context.age} ans, "
        f"yeux {context.yeux.lower()}, cheveux {context.cheveux.lower()}, "
        f"visage et morphologie identiques d'une image à l'autre. "
        f"Elle vit à {context.ville} ({context.pays}) et travaille comme "
        f"{context.profession.lower()}."
    )


def _pick(pool: list[str], context: AvatarContext, offset: int) -> str:
    return pool[(context.seed + context.variant_index * 3 + offset) % len(pool)]


def _interest_hint(context: AvatarContext) -> str:
    """Rattache le décor à un centre d'intérêt réel du profil, quand il y en a."""
    interests = [part.strip() for part in context.centres_interet.split(";") if part.strip()]
    if not interests:
        return ""
    chosen = interests[(context.seed + context.variant_index) % len(interests)]
    return f" Un détail discret du décor évoque son goût pour : {chosen.lower()}."


def build_avatar_prompt(context: AvatarContext) -> str:
    directive = STYLE_DIRECTIVES[context.style]

    if context.variant_index == 0:
        scene = (
            f"{MAIN_SHEET_INTRO} {MAIN_SHOT}, arrière-plan simple et peu contrasté, "
            f"visage bien éclairé."
        )
    else:
        scene = (
            f"Prise n°{context.variant_index + 1} : "
            f"{_pick(FRAMINGS, context, 0)}, "
            f"{_pick(SETTINGS, context, 1)}. "
            f"Tenue : {_pick(OUTFITS, context, 2)}. "
            f"{_pick(LIGHTS, context, 4).capitalize()}."
            f"{_interest_hint(context)}"
        )

    return (
        f"{directive} Cadre vertical, format 3:4.\n\n"
        f"Personnage : {build_character_sheet(context)}\n\n"
        f"{scene}\n\n"
        f"{NEGATIVE_DIRECTIVE} "
        "Le personnage est imaginaire : ne reproduis les traits d'aucune personne "
        "réelle ou célèbre."
    )


MAIN_SHEET_INTRO = "Photo principale du profil :"
