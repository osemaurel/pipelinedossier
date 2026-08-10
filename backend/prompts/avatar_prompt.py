"""Prompts de génération des avatars.

Les visuels imitent des photos personnelles ordinaires — selfies au téléphone,
décors du quotidien — parce que c'est ce à quoi ressemble une galerie de profil.
Le rendu vise l'appareil photo de téléphone, pas le portrait de studio : c'est
l'éclairage de studio et le lissage de peau qui trahissent une image fabriquée.

La cohérence du personnage vient d'une fiche physique stable, partagée par toutes
ses images. La variété vient du lieu, de la tenue, de la pose et de l'heure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AvatarStyle(str, Enum):
    PHOTO = "photo"
    ILLUSTRATION = "illustration"


# Esthétique « photo de téléphone ». Les termes de photographie professionnelle
# (studio, 50 mm, bokeh crémeux) sont volontairement absents : ils produisent le
# rendu lisse et publicitaire qui se repère au premier coup d'œil.
PHOTO_DIRECTIVE = (
    "Photo personnelle prise au téléphone. Rendu d'appareil photo de smartphone : "
    "netteté correcte sans excès, léger bruit numérique, lumière ambiante réelle "
    "non contrôlée, balance des blancs imparfaite. "
    "Peau naturelle avec sa texture, ses pores et ses irrégularités — aucun lissage, "
    "aucun filtre de beauté, aucune retouche. Cadrage spontané, légèrement de travers. "
    "Ce doit ressembler à une photo prise sur le vif, pas à une séance photo."
)

ILLUSTRATION_DIRECTIVE = (
    "Illustration numérique de portrait, style vectoriel contemporain : aplats de "
    "couleur, ombrage doux, traits nets, arrière-plan simplifié."
)

NEGATIVE_DIRECTIVE = (
    "Elle est seule sur l'image. Pas de texte, pas de logo, pas de filigrane. "
    "Tenue de tous les jours, couvrante ; cadrage non suggestif. "
    "Personnage imaginaire : ne reproduis les traits d'aucune personne réelle ou célèbre."
)

# Première image de la galerie : le visage doit être lisible, c'est la vignette.
MAIN_SHOT = (
    "Selfie tenu à bout de bras, visage bien visible et net, regard vers l'objectif, "
    "sourire naturel"
)

# La pose est décrite dans la scène elle-même : séparer les deux produisait des
# combinaisons impossibles (« appuyée au plan de travail, assise les genoux repliés »).
SCENES: list[str] = [
    "selfie assise sur son lit, adossée aux oreillers, chambre en désordre léger derrière elle",
    "selfie devant le miroir de l'entrée, téléphone visible dans la main, hanche déhanchée",
    "selfie sur le canapé du salon, genoux repliés sous elle, télévision allumée derrière",
    "selfie dans la rue, marchant, façades et passants flous derrière elle",
    "selfie à une table de café, penchée vers l'objectif, tasse posée devant elle",
    "selfie côté passager d'une voiture, ceinture visible, tête appuyée au dossier",
    "selfie sur le balcon, accoudée à la rambarde, immeubles et ciel derrière elle",
    "selfie dans un parc, assise dans l'herbe, une main dans les cheveux",
    "selfie dans la cuisine, debout appuyée contre le plan de travail",
    "selfie dans le couloir avant de sortir, sac à l'épaule",
    "photo prise par quelqu'un d'autre : elle marche dans la rue et se retourne",
    "selfie assise sur une marche d'escalier, coudes sur les genoux",
]

OUTFITS: list[str] = [
    "t-shirt uni et jean",
    "sweat à capuche ample",
    "robe d'été à fleurs",
    "chemisier léger et pantalon",
    "pull en maille et leggings",
    "débardeur et veste en jean",
    "robe longue en tissu imprimé",
    "haut à manches longues et jupe midi",
]

# « {} » reçoit la couleur de cheveux du profil, pour que l'accord soit correct.
HAIR_STYLES: list[str] = [
    "cheveux {} bouclés lâchés sur les épaules",
    "cheveux {} tressés en nattes collées",
    "cheveux {} lissés attachés en queue-de-cheval",
    "cheveux {} coupés au carré",
    "cheveux {} longs et ondulés",
    "cheveux {} relevés en chignon un peu défait",
    "locks {} mi-longues",
]

LIGHTS: list[str] = [
    "lumière du jour entrant par une fenêtre",
    "plafonnier d'intérieur, lumière jaune",
    "plein jour, ciel couvert",
    "fin d'après-midi, lumière rasante",
    "éclairage d'intérieur faible, léger grain",
    "soleil direct, ombres marquées",
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
    style: AvatarStyle = AvatarStyle.PHOTO
    seed: int = field(default=0)

    def __post_init__(self) -> None:
        # Décalage stable par personne : chaque profil suit sa propre séquence de
        # décors, mais reste reproductible d'une génération à l'autre.
        self.seed = sum(ord(c) * (i + 1) for i, c in enumerate(self.code_femme))


def _pick(pool: list[str], context: AvatarContext, offset: int) -> str:
    return pool[(context.seed + context.variant_index * 5 + offset) % len(pool)]


def _stable(pool: list[str], context: AvatarContext, offset: int) -> str:
    """Trait constant sur toutes les images d'une même personne."""
    return pool[(context.seed + offset) % len(pool)]


def build_character_sheet(context: AvatarContext) -> str:
    """Fiche physique identique sur toutes les images du même profil."""
    hair = _stable(HAIR_STYLES, context, 0).format(context.cheveux.lower())
    return (
        f"Femme d'environ {context.age} ans, yeux {context.yeux.lower()}, {hair}. "
        "Même visage, même morphologie et même coiffure sur toutes les images."
    )


def build_avatar_prompt(context: AvatarContext) -> str:
    directive = (
        PHOTO_DIRECTIVE if context.style is AvatarStyle.PHOTO else ILLUSTRATION_DIRECTIVE
    )

    if context.variant_index == 0:
        scene = f"{MAIN_SHOT}, chez elle, lumière du jour."
    else:
        scene = (
            f"{_pick(SCENES, context, 1).capitalize()}. "
            f"{_pick(LIGHTS, context, 3).capitalize()}."
        )

    return (
        f"{directive} Format vertical 3:4.\n\n"
        f"{build_character_sheet(context)}\n"
        f"Tenue : {_pick(OUTFITS, context, 4)}.\n\n"
        f"{scene}\n\n"
        f"{NEGATIVE_DIRECTIVE}"
    )
