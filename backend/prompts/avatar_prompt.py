"""Prompts de génération des avatars.

Les visuels imitent des photos personnelles ordinaires — selfies au téléphone,
décors du quotidien — parce que c'est ce à quoi ressemble une galerie de profil.
Le rendu vise l'appareil photo de téléphone, pas le portrait de studio : c'est
l'éclairage de studio et le lissage de peau qui trahissent une image fabriquée.

La cohérence du personnage vient d'une fiche physique stable, partagée par toutes
ses images. La variété vient du lieu, de la tenue, de la pose et de l'heure.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from enum import Enum
from math import gcd


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

# Silhouettes franchement distinctes : une liste trop homogène donnait
# l'impression d'un même vêtement décliné en motifs.
OUTFITS: list[str] = [
    "t-shirt col rond et jean droit",
    "sweat à capuche ample et jogging",
    "robe d'été courte à bretelles",
    "chemisier boutonné rentré dans un pantalon droit",
    "pull en grosse maille et leggings",
    "débardeur et veste en jean",
    "robe longue en pagne, coupe droite",
    "jupe midi plissée et haut à manches longues",
    "ensemble de sport, brassière couvrante et legging",
    "chemise oversize portée ouverte sur un haut uni",
    "combinaison pantalon ceinturée",
    "blazer cintré sur un t-shirt et un pantalon fluide",
    "tunique brodée et pantalon large",
    "cardigan long ouvert sur une robe droite",
    "polo et short en toile",
    "gilet sans manches et chemise à carreaux",
    "robe portefeuille nouée à la taille",
    "haut en crochet et jupe longue fendue",
]

# Axe indépendant de la coupe : deux robes ne se ressemblent pas si leur
# matière et leur gamme de couleur diffèrent.
FABRICS: list[str] = [
    "en coton uni bleu marine",
    "en lin beige",
    "en wax aux motifs géométriques verts et jaunes",
    "en jersey gris chiné",
    "dans un imprimé floral rouge et blanc",
    "en denim brut",
    "en satin bordeaux",
    "en maille écrue",
    "dans un ton kaki",
    "en tissu à rayures noires et blanches",
    "en velours côtelé moutarde",
    "dans un orange terracotta",
    "en toile blanche",
    "dans un violet profond",
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


def _hash(*parts: str) -> int:
    """Empreinte bien mélangée.

    Une somme pondérée des caractères du code progresse de façon régulière d'un
    profil au suivant — de 8 exactement entre PAL-0001 et PAL-0002 — si bien que
    tout choix par reste modulo une liste de 8 éléments retombait sur la même
    entrée pour toutes les femmes. Un CRC casse cette régularité : deux codes
    voisins donnent des empreintes sans rapport.
    """
    return zlib.crc32("|".join(parts).encode("utf-8"))


def _stable(pool: list[str], context: AvatarContext, salt: str) -> str:
    """Trait constant sur toutes les images d'une même personne."""
    return pool[_hash(context.code_femme, salt) % len(pool)]


def _coprime(start: int, size: int) -> int:
    """Premier entier ≥ start premier avec `size`, donc générateur d'un cycle complet."""
    step = max(1, start % size)
    while gcd(step, size) != 1:
        step += 1
    return step


def _profile_number(code: str) -> int | None:
    match = re.search(r"(\d+)\s*$", code)
    return int(match.group(1)) if match else None


def _varying(pool: list[str], context: AvatarContext, salt: str) -> str:
    """Choix propre à chaque image, étalé entre profils voisins.

    Un tirage par empreinte répartit bien en moyenne, mais forme des grappes :
    trois femmes sur douze recevaient la même coupe, et ce sont précisément les
    voisines d'une galerie qui se ressemblaient. Numéroter les profils et avancer
    d'un pas premier avec la taille de la liste parcourt tout le catalogue avant
    de revenir au début, ce qui rend deux profils consécutifs toujours distincts.
    """
    size = len(pool)
    number = _profile_number(context.code_femme)
    stride = _coprime(_hash(salt, "pas-profil"), size)
    if number is None:
        base = _hash(context.code_femme, salt) % size
    else:
        base = (number * stride + _hash(salt) % size) % size
    step = _coprime(_hash(context.code_femme, salt, "pas-image"), size)
    return pool[(base + context.variant_index * step) % size]


def build_character_sheet(context: AvatarContext) -> str:
    """Fiche physique identique sur toutes les images du même profil."""
    hair = _stable(HAIR_STYLES, context, "coiffure").format(context.cheveux.lower())
    return (
        f"Femme d'environ {context.age} ans, yeux {context.yeux.lower()}, {hair}. "
        "Même visage, même morphologie et même coiffure sur toutes les images."
    )


def build_outfit(context: AvatarContext) -> str:
    """Coupe et matière tirées séparément : la combinaison reste rare."""
    cut = _varying(OUTFITS, context, "tenue")
    fabric = _varying(FABRICS, context, "matiere")
    return f"{cut} {fabric}"


def build_avatar_prompt(context: AvatarContext) -> str:
    directive = (
        PHOTO_DIRECTIVE if context.style is AvatarStyle.PHOTO else ILLUSTRATION_DIRECTIVE
    )

    if context.variant_index == 0:
        scene = f"{MAIN_SHOT}, chez elle, lumière du jour."
    else:
        scene = (
            f"{_varying(SCENES, context, 'decor').capitalize()}. "
            f"{_varying(LIGHTS, context, 'lumiere').capitalize()}."
        )

    return (
        f"{directive} Format vertical 3:4.\n\n"
        f"{build_character_sheet(context)}\n"
        f"Tenue : {build_outfit(context)}.\n\n"
        f"{scene}\n\n"
        f"{NEGATIVE_DIRECTIVE}"
    )
