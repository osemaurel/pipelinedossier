"""Prompts de génération des profils et des agents. Aucune logique métier ici."""

from __future__ import annotations

from dataclasses import dataclass

SYSTEM_PROMPT = """\
Tu produis un jeu de données de DÉMONSTRATION pour une plateforme de discussion.

Nature des données — non négociable :
- Les personnages sont entièrement FICTIFS. Ils ne décrivent aucune personne réelle.
- N'utilise jamais le nom d'une personne réelle, connue ou publique.
- Aucune coordonnée réelle : les e-mails et téléphones sont ajoutés par le système,
  n'en invente pas.
- Ces profils servent à peupler un environnement de test, pas à représenter
  quelqu'un auprès de tiers.

Qualité attendue :
- Chaque personnage est cohérent de bout en bout : la profession correspond au
  niveau d'études, la ville au pays, la nationalité au pays de résidence, les
  centres d'intérêt à la présentation, l'âge recherché à l'âge du personnage.
- Les personnages d'un même lot sont nettement distincts : prénoms différents,
  professions variées, parcours variés, tournures de phrases variées.
- Interdiction d'ouvrir deux présentations par la même formule. Varie la structure
  des phrases, la longueur, le rythme, le point de départ du récit.
- Français naturel, à la première personne pour les textes de profil.
- Ton sobre et crédible. Pas de superlatifs publicitaires, pas d'emojis.

Tu réponds uniquement via le schéma JSON imposé."""


@dataclass(slots=True)
class ProfileBatchContext:
    count: int
    countries: list[str]
    cities: list[str]
    professions: list[str]
    birth_window: tuple[str, str]
    age_range: tuple[int, int]
    agent_codes: list[str]
    used_first_names: list[str]
    enum_values: dict[str, list[str]]
    length_rules: dict[str, tuple[int | None, int | None]]
    max_interests: int | None
    reference_date: str
    batch_index: int


def _format_lengths(rules: dict[str, tuple[int | None, int | None]]) -> str:
    lines = []
    for field, (low, high) in rules.items():
        if low and high:
            lines.append(f"- `{field}` : entre {low} et {high} caractères (bornes strictes).")
        elif high:
            lines.append(f"- `{field}` : {high} caractères maximum.")
    return "\n".join(lines)


def _format_enums(values: dict[str, list[str]]) -> str:
    return "\n".join(
        f"- `{field}` : {' | '.join(options)}" for field, options in values.items() if options
    )


def build_profile_prompt(context: ProfileBatchContext) -> str:
    low_age, high_age = context.age_range
    start, end = context.birth_window
    cities = ", ".join(context.cities) if context.cities else "villes principales des pays listés"
    professions = (
        ", ".join(context.professions)
        if context.professions
        else "professions plausibles et variées, cohérentes avec le niveau d'études"
    )
    avoid = (
        "\nPrénoms déjà utilisés dans ce dossier, à ne pas réutiliser : "
        + ", ".join(sorted(set(context.used_first_names)))
        if context.used_first_names
        else ""
    )

    return f"""\
Génère {context.count} personnages fictifs distincts (lot n°{context.batch_index}).

Date de référence : {context.reference_date}

Contraintes géographiques et démographiques :
- Pays de résidence à répartir parmi : {", ".join(context.countries)}
- Villes à utiliser : {cities}
- La ville doit réellement se situer dans le pays choisi pour le même personnage.
- La nationalité doit correspondre au pays de résidence (gentilé féminin).
- `date_naissance` au format AAAA-MM-JJ, comprise entre {start} et {end} inclus,
  ce qui donne un âge entre {low_age} et {high_age} ans à la date de référence.
- Professions à privilégier : {professions}
- `age_recherche_min` < `age_recherche_max`, tous deux plausibles au regard de
  l'âge du personnage.
- `taille_cm` entre 145 et 190. `poids_kg` entre 45 et 110, cohérent avec la taille.

Valeurs imposées — reprends la valeur exacte, sans reformuler ni accentuer autrement :
{_format_enums(context.enum_values)}

Champs libres :
- `prenom_affiche` : le prénom seul, extrait de `nom_legal_complet`.
- `ville_affichee` et `pays_affiche` : reprennent la ville et le pays de résidence.
- `langues` : format « Langue: niveau ; Langue: niveau », par exemple
  « Français: natif ; Anglais: intermédiaire ». Deux ou trois langues.
- `centres_interet` : {context.max_interests or 5} éléments maximum, séparés par « ; ».
  Ils doivent se retrouver en filigrane dans la présentation.

Longueurs de texte — comptées en caractères, espaces compris :
{_format_lengths(context.length_rules)}

Rappels de rédaction :
- `accroche` : une phrase, sans point final obligatoire, qui dit qui elle est.
- `presentation` : parcours, quotidien, ce qui compte pour elle. Première personne.
  INTERDIT d'y nommer sa ville ou son pays, ni d'y faire allusion — pas de
  « ici à Abidjan », pas de « dans mon pays », pas de quartier ni de région.
  Ces informations figurent déjà dans des colonnes dédiées.
- `recherche` : le type de relation et de personne recherchée. Première personne.
  INTERDIT d'y mentionner un âge, sous quelque forme que ce soit : ni « un homme
  de 40 ans », ni « entre 35 et 50 ans », ni « la quarantaine », ni « plus âgé
  que moi ». L'âge recherché est porté par deux colonnes séparées.
  Décris un caractère et une attente, pas un critère chiffré.
{avoid}"""


def build_content_fix_prompt(field: str, text: str, rule: str, low: int | None, high: int) -> str:
    """Réécriture d'un texte qui enfreint une règle de contenu.

    Utilisée quand le modèle a glissé une information proscrite malgré la
    consigne : plutôt que de signaler le problème, on fait corriger le texte.
    """
    length = f"entre {low} et {high}" if low else f"au maximum {high}"
    return f"""\
Le texte ci-dessous enfreint une règle : {rule}

Réécris-le en supprimant ce qui est proscrit, sans le remplacer par une
périphrase qui dirait la même chose. Garde la même personne grammaticale, le
même ton et le reste du contenu. Longueur attendue : {length} caractères, en
terminant sur une phrase complète. Renvoie uniquement le texte réécrit, sans
guillemets ni commentaire.

Champ : {field}

Texte :
{text}"""


def build_length_fix_prompt(field: str, text: str, low: int | None, high: int) -> str:
    target = f"entre {low} et {high}" if low else f"au maximum {high}"
    direction = (
        "Développe-le" if low and len(text) < low else "Resserre-le"
    )
    return f"""\
Le texte ci-dessous fait {len(text)} caractères. Il doit en faire {target}.

{direction} pour qu'il respecte cette longueur, en gardant la même personne
grammaticale, le même ton et l'essentiel du contenu. Termine sur une phrase
complète : ne tronque pas au milieu d'une idée. Renvoie uniquement le texte
réécrit, sans guillemets ni commentaire.

Champ : {field}

Texte :
{text}"""


AGENT_SYSTEM_PROMPT = """\
Tu produis des enregistrements d'agences FICTIVES pour un jeu de données de
démonstration. Aucune agence réelle, aucune raison sociale existante, aucune
personne réelle. Les coordonnées sont ajoutées par le système : n'en invente pas.
Tu réponds uniquement via le schéma JSON imposé."""


def build_agent_prompt(count: int, countries: list[str], codes: list[str]) -> str:
    return f"""\
Génère {count} agences fictives distinctes, correspondant aux codes {", ".join(codes)}.

- `nom_agence` : raison sociale plausible et inventée, sans reprendre le nom d'une
  entreprise existante.
- `personne_responsable` : nom complet fictif du contact, précédé de « M. » ou « Mme ».
- `pays` : à répartir parmi {", ".join(countries)}.
- `ville` : une ville réelle du pays retenu pour la même agence.
- `langues` : langues de travail, séparées par « ; ». Exemple : « Français ; Anglais »."""
