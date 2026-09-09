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
import unicodedata
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

# Deux familles de prises, alternées à la génération. Une galerie entièrement
# composée de selfies ne ressemble pas à un album de photos personnelles.
# La pose est décrite dans la scène : séparer les deux produisait des
# combinaisons impossibles (« appuyée au plan de travail, assise les genoux repliés »).
SELFIE_SCENES: list[tuple[str, bool]] = [
    ("selfie assise sur son lit, adossée aux oreillers, chambre en désordre léger derrière elle", False),
    ("selfie devant le miroir en pied de l'entrée, téléphone visible dans la main", False),
    ("selfie sur le canapé du salon, genoux repliés sous elle, télévision allumée derrière", False),
    ("selfie à une table de café, penchée vers l'objectif, tasse posée devant elle", False),
    ("selfie côté passager d'une voiture, ceinture visible, tête appuyée au dossier", True),
    ("selfie sur le balcon, accoudée à la rambarde, immeubles et ciel derrière elle", True),
    ("selfie dans la cuisine, debout appuyée contre le plan de travail", False),
    ("selfie dans le couloir avant de sortir, sac à l'épaule", False),
]

# Photos prises par quelqu'un d'autre : cadrages plus larges, sujet non centré,
# regard souvent ailleurs. C'est ce qui donne l'épaisseur d'un vrai album.
CANDID_SCENES: list[tuple[str, bool]] = [
    ("photo en pied prise par une amie, elle marche dans une rue commerçante et se retourne", True),
    ("photo prise de loin, assise sur un banc dans un parc, regard vers l'horizon", True),
    ("photo à table au restaurant, saisie en train de rire, verres et assiettes autour", False),
    ("photo en pied devant un mur coloré, bras le long du corps, posture décontractée", True),
    ("photo prise en marchant sur un marché, étals et passants autour d'elle", True),
    ("photo assise sur une marche d'escalier, plan large, coudes sur les genoux", True),
    ("photo au bord de l'eau, tournée vers l'objectif, plan taille", True),
    ("photo dans un salon avec une amie hors champ, elle est assise et regarde de côté", False),
    ("photo en pied à l'arrêt de bus, sac à l'épaule, ville autour", True),
    ("photo prise pendant une fête de famille, plan poitrine, guirlandes en arrière-plan", False),
]

# Carnations, tirées de façon stable par profil et cohérentes avec la région.
# Sans cette précision, la même femme sortait claire sur une image et foncée sur
# une autre : le modèle n'avait aucune contrainte de peau.
COMPLEXIONS_AFRIQUE_OUEST: list[str] = [
    "peau noire profonde",
    "peau noire, teinte ébène",
    "peau brun foncé",
    "peau brun moyen",
    "peau brun chaud, sous-ton doré",
]
COMPLEXIONS_MAGHREB: list[str] = [
    "peau mate, sous-ton olive",
    "peau brun clair",
    "peau claire hâlée",
]
MAGHREB = {"maroc", "tunisie", "algerie", "libye", "egypte"}

# Traits stables par personne : sans repères précis, chaque image redessinait un
# visage différent.
FACE_SHAPES: list[str] = [
    "visage ovale aux pommettes hautes",
    "visage rond aux joues pleines",
    "visage en cœur, menton fin",
    "visage allongé, mâchoire douce",
    "visage carré, mâchoire marquée",
]
FEATURES: list[str] = [
    "nez droit et fin, lèvres pleines",
    "nez large, lèvres bien dessinées",
    "nez court et retroussé, bouche menue",
    "nez aquilin, lèvres fines",
    "nez droit, lèvres charnues et arc de Cupidon marqué",
]
MARKS: list[str] = [
    "un grain de beauté sous l'œil gauche",
    "des fossettes quand elle sourit",
    "un petit espace entre les incisives",
    "des sourcils épais et bien dessinés",
    "une fine cicatrice au-dessus du sourcil droit",
    "des taches de rousseur discrètes sur les pommettes",
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

LIGHTS_INDOOR: list[str] = [
    "lumière du jour entrant par une fenêtre",
    "plafonnier d'intérieur, lumière jaune",
    "éclairage d'intérieur faible, léger grain",
    "lampe de chevet allumée, ambiance chaude",
]

LIGHTS_OUTDOOR: list[str] = [
    "plein jour, ciel couvert",
    "fin d'après-midi, lumière rasante",
    "soleil direct, ombres marquées",
    "début de matinée, lumière claire",
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
    # Le classeur porte déjà taille et poids : les ignorer laissait la
    # corpulence changer d'une image à l'autre.
    taille_cm: int = 0
    poids_kg: int = 0
    nationalite: str = ""


def normalise(text: str) -> str:
    """Sans accents ni casse, pour comparer un pays quelle que soit sa graphie."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


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


def _varying_index(size: int, context: AvatarContext, salt: str) -> int:
    """Rang tiré pour cette image, étalé entre profils voisins.

    Un tirage par empreinte répartit bien en moyenne, mais forme des grappes :
    trois femmes sur douze partageaient une coupe, et ce sont justement les
    voisines d'une galerie qui se remarquent. Numéroter les profils et avancer
    d'un pas premier avec la taille de la liste balaie tout le catalogue avant
    de reboucler, ce qui rend deux profils consécutifs toujours distincts.
    """
    number = _profile_number(context.code_femme)
    stride = _coprime(_hash(salt, "pas-profil"), size)
    if number is None:
        base = _hash(context.code_femme, salt) % size
    else:
        base = (number * stride + _hash(salt) % size) % size
    step = _coprime(_hash(context.code_femme, salt, "pas-image"), size)
    return (base + context.variant_index * step) % size


def _varying(pool: list[str], context: AvatarContext, salt: str) -> str:
    """Entrée tirée pour cette image, selon la même répartition étalée."""
    return pool[_varying_index(len(pool), context, salt)]


def _build(context: AvatarContext) -> str:
    """Corpulence déduite de la taille et du poids réellement portés au dossier."""
    if context.taille_cm <= 0 or context.poids_kg <= 0:
        return "silhouette moyenne"
    imc = context.poids_kg / (context.taille_cm / 100) ** 2
    if imc < 19:
        silhouette = "silhouette mince, épaules étroites"
    elif imc < 25:
        silhouette = "silhouette moyenne, proportions équilibrées"
    elif imc < 30:
        silhouette = "silhouette pulpeuse, hanches marquées"
    else:
        silhouette = "silhouette forte, corpulence généreuse"
    return f"{context.taille_cm} cm, {silhouette}"


def _complexion(context: AvatarContext) -> str:
    origine = normalise(f"{context.pays} {context.nationalite}")
    palette = (
        COMPLEXIONS_MAGHREB
        if any(pays in origine for pays in MAGHREB)
        else COMPLEXIONS_AFRIQUE_OUEST
    )
    return _stable(palette, context, "carnation")


def build_character_sheet(context: AvatarContext) -> str:
    """Fiche physique identique sur toutes les images du même profil.

    Elle est volontairement détaillée : carnation, corpulence et traits du visage
    étaient absents, et rien n'empêchait le modèle de redessiner une personne
    différente à chaque image.
    """
    hair = _stable(HAIR_STYLES, context, "coiffure").format(context.cheveux.lower())
    return (
        f"TOUJOURS LA MÊME FEMME, trait pour trait, sur toutes les images de cette série.\n"
        f"- Âge : environ {context.age} ans\n"
        f"- Carnation : {_complexion(context)}, identique sur chaque image\n"
        f"- Corpulence : {_build(context)}, identique sur chaque image\n"
        f"- Visage : {_stable(FACE_SHAPES, context, 'visage')}, "
        f"{_stable(FEATURES, context, 'traits')}\n"
        f"- Yeux : {context.yeux.lower()}\n"
        f"- Cheveux : {hair}\n"
        f"- Signe particulier : {_stable(MARKS, context, 'signe')}\n"
        f"Ne modifie ni la couleur de peau, ni la corpulence, ni la forme du visage "
        f"d'une image à l'autre."
    )


def build_outfit(context: AvatarContext) -> str:
    """Coupe et matière tirées séparément : la combinaison reste rare."""
    cut = _varying(OUTFITS, context, "tenue")
    fabric = _varying(FABRICS, context, "matiere")
    return f"{cut} {fabric}"


def build_scene(context: AvatarContext) -> str:
    """Alterne selfies et photos prises par un tiers.

    Choisir dans une liste unique donnait huit selfies quand on demandait huit
    photos : l'alternance est imposée par le rang de l'image, pas laissée au
    hasard du tirage. La lumière suit le décor — une scène de rue éclairée au
    plafonnier trahissait immédiatement l'image.
    """
    if context.variant_index == 0:
        return f"{MAIN_SHOT}, chez elle, lumière du jour."

    candid = context.variant_index % 2 == 1
    pool = CANDID_SCENES if candid else SELFIE_SCENES
    index = _varying_index(len(pool), context, "candide" if candid else "selfie")
    scene, outdoor = pool[index]
    lights = LIGHTS_OUTDOOR if outdoor else LIGHTS_INDOOR
    light = lights[_varying_index(len(lights), context, "lumiere")]
    return f"{scene.capitalize()}. {light.capitalize()}."


def build_avatar_prompt(context: AvatarContext) -> str:
    directive = (
        PHOTO_DIRECTIVE if context.style is AvatarStyle.PHOTO else ILLUSTRATION_DIRECTIVE
    )
    return (
        f"{directive} Format vertical 3:4.\n\n"
        f"{build_character_sheet(context)}\n\n"
        f"Tenue : {build_outfit(context)}.\n\n"
        f"{build_scene(context)}\n\n"
        f"{NEGATIVE_DIRECTIVE}"
    )


REFERENCE_DIRECTIVE = (
    "L'image fournie montre cette femme. Reprends EXACTEMENT le même visage, la "
    "même couleur de peau, la même corpulence et la même coiffure : c'est une "
    "autre photo de la même personne, prise un autre jour. Seuls la tenue, le "
    "décor, la pose et la lumière changent."
)


def build_reference_prompt(context: AvatarContext) -> str:
    """Prompt d'une image dérivée d'une photo de référence de la même femme."""
    directive = (
        PHOTO_DIRECTIVE if context.style is AvatarStyle.PHOTO else ILLUSTRATION_DIRECTIVE
    )
    return (
        f"{directive} Format vertical 3:4.\n\n"
        f"{REFERENCE_DIRECTIVE}\n\n"
        f"Tenue : {build_outfit(context)}.\n\n"
        f"{build_scene(context)}\n\n"
        f"{NEGATIVE_DIRECTIVE}"
    )
