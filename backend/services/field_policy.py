"""Classification des colonnes du modèle en modes de remplissage.

Ce module est le point unique où l'on décide, pour chaque colonne détectée dans
le classeur, *qui* la remplit : Excel (formule), le générateur déterministe, le
modèle de langage, ou une valeur de politique fixe.

Les colonnes de vérification (pièce d'identité, contrat de mandat, consentement)
ne sont jamais fabriquées : elles n'enregistrent pas une donnée mais le fait
qu'un humain a contrôlé un document. Les renseigner automatiquement pour un
personnage inexistant produirait précisément le résultat que ce contrôle sert à
rendre infalsifiable. Le « Lisez-moi » du modèle prévoit ce cas : un dossier
incomplet reste importable et attend côté administration.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.services.excel_introspect import ColumnSchema, SheetSchema

WITHHELD_VALUE = "N/A — démonstration"
FICTION_NOTE = (
    "PERSONNAGE FICTIF — profil de démonstration généré automatiquement. "
    "Ne correspond à aucune personne réelle. Vérifications non effectuées."
)
AGENT_FICTION_NOTE = (
    "AGENT FICTIF — enregistrement de démonstration généré automatiquement."
)
DEFAULT_STATUS = "À compléter"


class FillMode(str, Enum):
    COMPUTED = "computed"          # formule Excel, recopiée telle quelle
    ASSIGNED = "assigned"          # code déterministe (PAL-0001, AG-01)
    GENERATED = "generated"        # produit par le modèle de langage
    CONTACT = "contact"            # coordonnée fictive en domaine réservé
    WITHHELD = "withheld"          # colonne de vérification : jamais fabriquée
    STATUS = "status"              # statut de dossier, forcé au plus bas
    MEDIA_COUNT = "media_count"    # compté sur les fichiers réellement produits
    NOTES = "notes"                # marqueur « fictif »
    FIXED = "fixed"                # valeur constante


@dataclass(slots=True)
class FieldSpec:
    column: ColumnSchema
    mode: FillMode
    name: str
    fixed_value: str | None = None


# (fragments de clé, mode, nom canonique, valeur fixe éventuelle).
# L'ordre compte : la première règle qui correspond gagne.
_FEMME_RULES: list[tuple[tuple[str, ...], FillMode, str, str | None]] = [
    (("code", "femme"), FillMode.ASSIGNED, "code_femme", None),
    (("code", "agent"), FillMode.ASSIGNED, "code_agent", None),
    (("piece",), FillMode.WITHHELD, "piece_identite", None),
    (("numero",), FillMode.WITHHELD, "numero_piece", None),
    (("contrat",), FillMode.WITHHELD, "contrat_mandat", None),
    (("signature",), FillMode.WITHHELD, "date_signature", None),
    (("consentement",), FillMode.WITHHELD, "consentement_photos", None),
    (("mail",), FillMode.CONTACT, "email", None),
    (("telephone",), FillMode.CONTACT, "telephone", None),
    (("statut",), FillMode.STATUS, "statut_dossier", None),
    (("nombre", "photos"), FillMode.MEDIA_COUNT, "nombre_photos", None),
    (("video",), FillMode.FIXED, "video_fournie", "Non"),
    (("notes",), FillMode.NOTES, "notes_internes", None),
    (("nom", "legal"), FillMode.GENERATED, "nom_legal_complet", None),
    (("date", "naissance"), FillMode.GENERATED, "date_naissance", None),
    (("nationalite",), FillMode.GENERATED, "nationalite", None),
    (("pays", "residence"), FillMode.GENERATED, "pays_residence", None),
    (("ville", "residence"), FillMode.GENERATED, "ville_residence", None),
    (("prenom", "affiche"), FillMode.GENERATED, "prenom_affiche", None),
    (("ville", "affichee"), FillMode.GENERATED, "ville_affichee", None),
    (("pays", "affiche"), FillMode.GENERATED, "pays_affiche", None),
    (("langues",), FillMode.GENERATED, "langues", None),
    (("situation",), FillMode.GENERATED, "situation", None),
    (("enfants",), FillMode.GENERATED, "enfants", None),
    (("profession",), FillMode.GENERATED, "profession", None),
    (("etudes",), FillMode.GENERATED, "niveau_etudes", None),
    (("taille",), FillMode.GENERATED, "taille_cm", None),
    (("poids",), FillMode.GENERATED, "poids_kg", None),
    (("yeux",), FillMode.GENERATED, "yeux", None),
    (("cheveux",), FillMode.GENERATED, "cheveux", None),
    (("religion",), FillMode.GENERATED, "religion", None),
    (("tabac",), FillMode.GENERATED, "tabac", None),
    (("alcool",), FillMode.GENERATED, "alcool", None),
    (("centres",), FillMode.GENERATED, "centres_interet", None),
    (("relation",), FillMode.GENERATED, "type_relation", None),
    (("age", "min"), FillMode.GENERATED, "age_recherche_min", None),
    (("age", "max"), FillMode.GENERATED, "age_recherche_max", None),
    (("demenager",), FillMode.GENERATED, "prete_a_demenager", None),
    (("accroche",), FillMode.GENERATED, "accroche", None),
    (("presentation",), FillMode.GENERATED, "presentation", None),
    (("recherche",), FillMode.GENERATED, "recherche", None),
]

_AGENT_RULES: list[tuple[tuple[str, ...], FillMode, str, str | None]] = [
    (("code", "agent"), FillMode.ASSIGNED, "code_agent", None),
    (("contrat",), FillMode.WITHHELD, "contrat_cadre", None),
    (("date", "contrat"), FillMode.WITHHELD, "date_contrat", None),
    (("mail",), FillMode.CONTACT, "email", None),
    (("telephone",), FillMode.CONTACT, "telephone", None),
    (("notes",), FillMode.NOTES, "notes", None),
    (("nom",), FillMode.GENERATED, "nom_agence", None),
    (("responsable",), FillMode.GENERATED, "personne_responsable", None),
    (("pays",), FillMode.GENERATED, "pays", None),
    (("ville",), FillMode.GENERATED, "ville", None),
    (("langues",), FillMode.GENERATED, "langues", None),
]


def _classify(column: ColumnSchema, rules: list[tuple[tuple[str, ...], FillMode, str, str | None]],
              used: set[str]) -> FieldSpec:
    if column.is_formula:
        return FieldSpec(column=column, mode=FillMode.COMPUTED, name=column.key)
    for fragments, mode, name, fixed in rules:
        if name in used:
            continue
        if all(fragment in column.key for fragment in fragments):
            used.add(name)
            return FieldSpec(column=column, mode=mode, name=name, fixed_value=fixed)
    # Colonne inconnue : on ne devine pas, on laisse vide plutôt que d'inventer.
    return FieldSpec(column=column, mode=FillMode.FIXED, name=column.key, fixed_value=None)


def build_femme_specs(sheet: SheetSchema) -> list[FieldSpec]:
    used: set[str] = set()
    return [_classify(column, _FEMME_RULES, used) for column in sheet.columns]


def build_agent_specs(sheet: SheetSchema) -> list[FieldSpec]:
    used: set[str] = set()
    return [_classify(column, _AGENT_RULES, used) for column in sheet.columns]


def generated_specs(specs: list[FieldSpec]) -> list[FieldSpec]:
    return [spec for spec in specs if spec.mode is FillMode.GENERATED]


def spec_by_name(specs: list[FieldSpec], name: str) -> FieldSpec | None:
    return next((spec for spec in specs if spec.name == name), None)
