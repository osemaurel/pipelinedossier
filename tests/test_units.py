"""Tests unitaires des briques qui ne dépendent pas d'un appel réseau."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from backend.services.excel_introspect import introspect, normalize, retarget_ranges
from backend.services.field_policy import (
    FillMode,
    build_agent_specs,
    build_femme_specs,
    spec_by_name,
)
from backend.services.image_generator import stamp_provenance
from backend.services.profile_generator import (
    birth_window,
    build_json_schema,
    demo_email,
    demo_phone,
    sentence_safe_trim,
)

TEMPLATE = Path("palabdossiercollecte.xlsx")


@pytest.fixture(scope="module")
def schema():
    return introspect(TEMPLATE)


def test_normalize_strips_accents_and_parentheses():
    assert normalize("Accroche (120 caractères max)") == "accroche"
    assert normalize("Niveau d'études") == "niveau d etudes"
    assert normalize("Âge recherché — min") == "age recherche min"


def test_introspection_finds_real_header_row(schema):
    """La feuille Femmes a une ligne de bandes fusionnées au-dessus des en-têtes."""
    assert schema.femmes.header_row == 2
    assert schema.femmes.example_row == 3
    assert len(schema.femmes.columns) == 45
    assert schema.femmes.by_key("code femme") is not None


def test_length_bounds_come_from_control_formulas(schema):
    """Les formules sont plus précises que les en-têtes : elles portent le minimum."""
    constraints = schema.text_constraints()
    assert constraints["accroche"] == (40, 120)
    assert constraints["presentation"] == (600, 1200)
    assert constraints["ce que je recherche"] == (200, 400)


def test_dropdown_values_are_resolved_from_listes_sheet(schema):
    situation = schema.femmes.find("situation")
    assert situation is not None
    assert situation.allowed_values == ["Célibataire", "Divorcée", "Veuve", "Séparée"]


def test_formula_templates_are_row_parameterised(schema):
    age = schema.femmes.by_key("age")
    assert age is not None
    assert age.formula_template == '=IF(D{row}="","",DATEDIF(D{row},TODAY(),"Y"))'


def test_retarget_ranges_only_touches_the_named_sheet():
    formula = '=IF(A2="","",COUNTIF(Femmes!$B$4:$B$153,A2))'
    assert retarget_ranges(formula, "Femmes", 3, 162) == (
        '=IF(A2="","",COUNTIF(Femmes!$B$3:$B$162,A2))'
    )
    assert retarget_ranges(formula, "Photos", 3, 162) == formula


def test_verification_columns_are_never_generated(schema):
    specs = build_femme_specs(schema.femmes)
    withheld = {spec.name for spec in specs if spec.mode is FillMode.WITHHELD}
    assert withheld == {
        "piece_identite", "numero_piece", "contrat_mandat",
        "date_signature", "consentement_photos",
    }
    assert spec_by_name(specs, "statut_dossier").mode is FillMode.STATUS
    assert spec_by_name(specs, "email").mode is FillMode.CONTACT


def test_agent_columns_are_classified(schema):
    specs = build_agent_specs(schema.agents)
    assert spec_by_name(specs, "code_agent").mode is FillMode.ASSIGNED
    assert spec_by_name(specs, "nom_agence").mode is FillMode.GENERATED
    assert any(spec.mode is FillMode.COMPUTED for spec in specs)


def test_json_schema_is_strict_and_carries_enums(schema):
    specs = build_femme_specs(schema.femmes)
    built = build_json_schema(specs, "profils")
    item = built["properties"]["profils"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])
    assert "piece_identite" not in item["properties"]
    assert item["properties"]["situation"]["enum"] == ["Célibataire", "Divorcée", "Veuve", "Séparée"]
    assert item["properties"]["taille_cm"]["type"] == "integer"


def test_json_schema_filters_narrow_but_never_widen(schema):
    specs = build_femme_specs(schema.femmes)
    built = build_json_schema(
        specs, "profils", {"situation": ["Divorcée", "Valeur inexistante"]}
    )
    assert built["properties"]["profils"]["items"]["properties"]["situation"]["enum"] == ["Divorcée"]


def test_birth_window_matches_requested_ages():
    reference = date(2026, 8, 10)
    oldest, youngest = birth_window(25, 45, reference)
    for born in (oldest, youngest):
        age = reference.year - born.year - ((reference.month, reference.day) < (born.month, born.day))
        assert 25 <= age <= 45


def test_demo_contacts_use_reserved_ranges():
    assert demo_email("Aminata", "PAL-0001").endswith("@example.test")
    assert demo_phone(7).startswith("+99")


def test_sentence_safe_trim_never_cuts_mid_sentence():
    text = "Première phrase complète. Deuxième phrase un peu plus longue. Troisième phrase."
    trimmed = sentence_safe_trim(text, 40)
    assert len(trimmed) <= 40
    assert trimmed.endswith(".")
    assert trimmed == "Première phrase complète."


def test_sentence_safe_trim_keeps_short_text_untouched():
    assert sentence_safe_trim("Court.", 100) == "Court."


def test_png_provenance_chunk_is_inserted():
    png = (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR" + b"\x00" * 13 + b"\x00\x00\x00\x00"
        + b"\x00\x00\x00\x00IEND\xae B`\x82"
    )
    stamped = stamp_provenance(png)
    assert b"Palab Dossier Generator" in stamped
    assert stamped.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"IHDR" in stamped[:30]


def test_stamp_provenance_ignores_non_png():
    assert stamp_provenance(b"pas une image") == b"pas une image"
