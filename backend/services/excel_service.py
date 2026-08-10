"""Écriture du dossier final à partir d'une copie du modèle.

Le fichier source n'est jamais ouvert en écriture : on le copie, puis on remplit
la copie. Les feuilles, styles, largeurs, listes déroulantes et formules du
modèle sont conservés ; les formules sont recopiées vers les lignes ajoutées et
leurs plages inter-feuilles réalignées sur l'étendue réelle des données.
"""

from __future__ import annotations

import shutil
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from backend.core.logging import get_logger
from backend.models.schemas import Agent, PhotoRow, Profile
from backend.services.excel_introspect import SheetSchema, WorkbookSchema, retarget_ranges
from backend.services.field_policy import (
    AGENT_FICTION_NOTE,
    DEFAULT_STATUS,
    FICTION_NOTE,
    FieldSpec,
    FillMode,
    WITHHELD_VALUE,
)

logger = get_logger(__name__)


def _copy_style(target: object, source: object) -> None:
    target._style = source._style  # type: ignore[attr-defined]  # noqa: SLF001


def _prepare_row(ws: Worksheet, row: int, template_row: int, columns: int) -> None:
    """Aligne une ligne ajoutée sur le gabarit du modèle (styles + formules)."""
    if row <= template_row:
        return
    for col in range(1, columns + 1):
        source = ws.cell(row=template_row, column=col)
        target = ws.cell(row=row, column=col)
        _copy_style(target, source)


def _reset_example_row(ws: Worksheet, sheet: SheetSchema) -> None:
    """Neutralise la ligne d'exemple : contenu effacé, style aligné sur les lignes vierges."""
    if sheet.example_row is None:
        return
    clean_row = sheet.example_row + 1
    for col in range(1, len(sheet.columns) + 1):
        cell = ws.cell(row=sheet.example_row, column=col)
        cell.value = None
        if clean_row <= sheet.data_end_row:
            _copy_style(cell, ws.cell(row=clean_row, column=col))


def _extend_validations(ws: Worksheet, template_end: int, last_row: int) -> None:
    """Prolonge les listes déroulantes du modèle jusqu'aux lignes ajoutées.

    Les validations sont figées sur la capacité initiale ; au-delà, les lignes
    ajoutées perdraient leur menu déroulant et le contrôle de saisie.
    """
    if last_row <= template_end:
        return
    for validation in ws.data_validations.dataValidation:
        extended: list[str] = []
        for cell_range in validation.sqref.ranges:
            if cell_range.max_row == template_end:
                cell_range.max_row = last_row
            extended.append(str(cell_range))
        validation.sqref = " ".join(extended)


def _write_formula(ws: Worksheet, row: int, spec: FieldSpec) -> None:
    if spec.column.formula_template:
        ws.cell(row=row, column=spec.column.index).value = (
            spec.column.formula_template.format(row=row)
        )


def _coerce(value: object, spec: FieldSpec) -> object:
    if value is None or value == "":
        return None
    if spec.column.is_date and isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return value
    return value


def _set(ws: Worksheet, row: int, spec: FieldSpec, value: object) -> None:
    coerced = _coerce(value, spec)
    if coerced is None:
        return
    cell = ws.cell(row=row, column=spec.column.index)
    cell.value = coerced
    if spec.column.is_date and isinstance(coerced, datetime):
        cell.number_format = spec.column.number_format


class ExcelWriter:
    def __init__(self, schema: WorkbookSchema) -> None:
        self._schema = schema

    def write(
        self,
        *,
        source: Path,
        destination: Path,
        profiles: list[Profile],
        agents: list[Agent],
        photos: list[PhotoRow],
        femme_specs: list[FieldSpec],
        agent_specs: list[FieldSpec],
        reference: date,
    ) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

        wb = load_workbook(destination, data_only=False)
        try:
            photo_counts: dict[str, int] = {}
            for row in photos:
                photo_counts[row.code_femme] = photo_counts.get(row.code_femme, 0) + 1

            femmes_end = self._write_femmes(
                wb[self._schema.femmes.name], profiles, femme_specs, photo_counts
            )
            self._write_agents(
                wb[self._schema.agents.name], agents, agent_specs, femmes_end
            )
            if self._schema.photos is not None:
                self._write_photos(wb[self._schema.photos.name], photos)
            wb.save(destination)
        finally:
            wb.close()

        logger.info("Excel généré : %s", destination.name)
        return destination

    def _write_femmes(
        self,
        ws: Worksheet,
        profiles: list[Profile],
        specs: list[FieldSpec],
        photo_counts: dict[str, int],
    ) -> int:
        sheet = self._schema.femmes
        _reset_example_row(ws, sheet)
        template_row = sheet.data_end_row
        columns = len(sheet.columns)
        last_row = sheet.data_start_row

        for offset, profile in enumerate(profiles):
            row = sheet.data_start_row + offset
            last_row = row
            _prepare_row(ws, row, template_row, columns)
            for spec in specs:
                self._apply(ws, row, spec, profile, photo_counts)

        _extend_validations(ws, sheet.data_end_row, last_row)
        if len(profiles) > sheet.capacity:
            logger.info(
                "%d profils dépassent la capacité du modèle (%d lignes) : "
                "lignes ajoutées avec recopie des formules et des listes déroulantes.",
                len(profiles), sheet.capacity,
            )
        return max(last_row, sheet.data_end_row)

    def _apply(
        self,
        ws: Worksheet,
        row: int,
        spec: FieldSpec,
        profile: Profile,
        photo_counts: dict[str, int],
    ) -> None:
        match spec.mode:
            case FillMode.COMPUTED:
                _write_formula(ws, row, spec)
            case FillMode.WITHHELD:
                _set(ws, row, spec, WITHHELD_VALUE)
            case FillMode.STATUS:
                allowed = spec.column.allowed_values
                _set(ws, row, spec, DEFAULT_STATUS if DEFAULT_STATUS in allowed
                     else (allowed[0] if allowed else DEFAULT_STATUS))
            case FillMode.NOTES:
                _set(ws, row, spec, FICTION_NOTE)
            case FillMode.MEDIA_COUNT:
                _set(ws, row, spec, photo_counts.get(profile.code_femme, 0))
            case FillMode.FIXED:
                _set(ws, row, spec, spec.fixed_value)
            case _:
                _set(ws, row, spec, getattr(profile, spec.name, None))

    def _write_agents(
        self, ws: Worksheet, agents: list[Agent], specs: list[FieldSpec], femmes_end: int
    ) -> None:
        sheet = self._schema.agents
        _reset_example_row(ws, sheet)
        template_row = sheet.data_end_row
        columns = len(sheet.columns)
        femmes_start = self._schema.femmes.data_start_row

        last_row = sheet.data_start_row
        for offset, agent in enumerate(agents):
            row = sheet.data_start_row + offset
            last_row = row
            _prepare_row(ws, row, template_row, columns)
            for spec in specs:
                if spec.mode is FillMode.COMPUTED:
                    _write_formula(ws, row, spec)
                elif spec.mode is FillMode.WITHHELD:
                    _set(ws, row, spec, WITHHELD_VALUE)
                elif spec.mode is FillMode.NOTES:
                    _set(ws, row, spec, AGENT_FICTION_NOTE)
                elif spec.mode is FillMode.FIXED:
                    _set(ws, row, spec, spec.fixed_value)
                else:
                    _set(ws, row, spec, getattr(agent, spec.name, None))

        _extend_validations(ws, sheet.data_end_row, last_row)
        self._retarget_agent_formulas(
            ws, sheet, femmes_start, femmes_end, max(last_row, sheet.data_end_row)
        )

    def _retarget_agent_formulas(
        self, ws: Worksheet, sheet: SheetSchema, start: int, end: int, last_row: int
    ) -> None:
        """Réaligne `COUNTIF(Femmes!$B$4:$B$153; …)` sur l'étendue réelle.

        Le modèle fige la plage en excluant la ligne d'exemple. Comme cette ligne
        redevient une ligne de données, la borne basse doit descendre, sans quoi
        le premier profil ne serait pas compté.
        """
        femmes_name = self._schema.femmes.name
        for row in range(sheet.data_start_row, last_row + 1):
            for column in sheet.columns:
                if not column.is_formula:
                    continue
                cell = ws.cell(row=row, column=column.index)
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    cell.value = retarget_ranges(cell.value, femmes_name, start, end)

    def _write_photos(self, ws: Worksheet, photos: list[PhotoRow]) -> None:
        sheet = self._schema.photos
        assert sheet is not None
        _reset_example_row(ws, sheet)
        template_row = sheet.data_end_row
        columns = len(sheet.columns)

        code_col = sheet.find("code", "femme")
        file_col = sheet.find("fichier")
        order_col = sheet.find("ordre")
        caption_col = sheet.find("legende")
        notes_col = sheet.find("notes")

        for offset, photo in enumerate(photos):
            row = sheet.data_start_row + offset
            _prepare_row(ws, row, template_row, columns)
            for column, value in (
                (code_col, photo.code_femme),
                (file_col, photo.filename),
                (order_col, photo.order),
                (caption_col, photo.caption),
                (notes_col, photo.notes),
            ):
                if column is not None:
                    ws.cell(row=row, column=column.index).value = value
