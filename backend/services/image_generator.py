"""Génération des avatars, avec parallélisme borné et échec isolé par profil."""

from __future__ import annotations

import asyncio
import struct
import zlib
from datetime import date
from pathlib import Path
from typing import Awaitable, Callable

from backend.config import Settings
from backend.core.logging import get_logger
from backend.models.schemas import PhotoRow, Profile
from backend.prompts.avatar_prompt import (
    AvatarContext,
    AvatarStyle,
    build_avatar_prompt,
    build_reference_prompt,
)
from backend.services.openai_service import OpenAIService

logger = get_logger(__name__)

PROVENANCE = (
    "Avatar de synthèse généré par IA pour un jeu de données de démonstration. "
    "Ne représente aucune personne réelle."
)


def _png_text_chunk(keyword: str, text: str) -> bytes:
    payload = keyword.encode("latin-1", "replace") + b"\x00" + text.encode("latin-1", "replace")
    chunk_type = b"tEXt"
    crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)


def stamp_provenance(png: bytes) -> bytes:
    """Insère la provenance IA dans les métadonnées PNG, juste après l'en-tête IHDR."""
    signature = b"\x89PNG\r\n\x1a\n"
    if not png.startswith(signature):
        return png
    offset = len(signature)
    length = struct.unpack(">I", png[offset : offset + 4])[0]
    ihdr_end = offset + 8 + length + 4
    chunks = _png_text_chunk("Software", "Palab Dossier Generator")
    chunks += _png_text_chunk("Comment", PROVENANCE)
    return png[:ihdr_end] + chunks + png[ihdr_end:]


class ImageGenerator:
    def __init__(self, openai: OpenAIService, settings: Settings) -> None:
        self._openai = openai
        self._semaphore = asyncio.Semaphore(max(1, settings.image_concurrency))
        try:
            self._style = AvatarStyle(settings.openai_image_style.strip().lower())
        except ValueError:
            logger.warning(
                "OPENAI_IMAGE_STYLE=%r inconnu, repli sur « illustration ». "
                "Valeurs acceptées : illustration, photo.",
                settings.openai_image_style,
            )
            self._style = AvatarStyle.ILLUSTRATION

    async def generate_for_profiles(
        self,
        profiles: list[Profile],
        per_profile: int,
        photos_dir: Path,
        reference: date,
        on_progress: Callable[[int], Awaitable[None]] | None = None,
        existing: set[str] | None = None,
    ) -> tuple[list[PhotoRow], dict[str, str]]:
        """Renvoie les lignes de la feuille Photos et les échecs par code femme."""
        photos_dir.mkdir(parents=True, exist_ok=True)
        done = existing or set()
        rows: list[PhotoRow] = []
        failures: dict[str, str] = {}
        counter = 0
        lock = asyncio.Lock()

        def make_context(profile: Profile, order: int) -> AvatarContext:
            return AvatarContext(
                code_femme=profile.code_femme,
                age=profile.age_at(reference) or 30,
                ville=profile.ville_affichee or profile.ville_residence,
                pays=profile.pays_affiche or profile.pays_residence,
                profession=profile.profession,
                yeux=profile.yeux,
                cheveux=profile.cheveux,
                variant_index=order - 1,
                centres_interet=profile.centres_interet,
                style=self._style,
                taille_cm=profile.taille_cm,
                poids_kg=profile.poids_kg,
                nationalite=profile.nationalite,
            )

        async def render(context: AvatarContext, anchor: bytes | None) -> bytes:
            """Produit une image, ancrée sur la première photo quand elle existe."""
            if anchor is None:
                return await self._openai.image_png(build_avatar_prompt(context))
            try:
                return await self._openai.image_png_from_reference(
                    build_reference_prompt(context), anchor
                )
            except Exception as exc:  # noqa: BLE001
                # Une passerelle compatible OpenAI peut ne pas servir la retouche
                # d'image : mieux vaut une photo moins fidèle que pas de photo.
                logger.warning(
                    "Variation depuis référence indisponible (%s) : repli sur une "
                    "génération décrite pour %s.", type(exc).__name__, context.code_femme,
                )
                return await self._openai.image_png(build_avatar_prompt(context))

        async def one(profile: Profile, order: int, anchor: bytes | None) -> PhotoRow | None:
            nonlocal counter
            filename = f"{profile.code_femme}_avatar_{order:02d}.png"
            target = photos_dir / filename
            context = make_context(profile, order)
            try:
                if filename in done and target.exists():
                    logger.info("Avatar déjà présent, réutilisé : %s", filename)
                else:
                    async with self._semaphore:
                        png = await render(context, anchor)
                    target.write_bytes(stamp_provenance(png))
            except Exception as exc:  # noqa: BLE001 — un échec n'arrête pas le dossier
                logger.error("Avatar %s en échec : %s", filename, exc)
                async with lock:
                    failures[profile.code_femme] = str(exc)
                return None

            async with lock:
                counter += 1
                if on_progress:
                    await on_progress(counter)

            return PhotoRow(
                code_femme=profile.code_femme,
                filename=filename,
                order=order,
                caption=f"Avatar de synthèse {order} — {context.ville}".strip(" —"),
                notes=PROVENANCE,
            )

        async def gallery(profile: Profile) -> list[PhotoRow]:
            """La première photo sert de référence visuelle aux suivantes."""
            first = await one(profile, 1, None)
            produced = [first] if first else []
            if per_profile < 2:
                return produced

            anchor: bytes | None = None
            portrait = photos_dir / f"{profile.code_femme}_avatar_01.png"
            if portrait.exists():
                anchor = portrait.read_bytes()

            rest = await asyncio.gather(
                *(one(profile, order, anchor) for order in range(2, per_profile + 1))
            )
            produced.extend(row for row in rest if row is not None)
            return produced

        for gallery_rows in await asyncio.gather(*(gallery(p) for p in profiles)):
            rows.extend(gallery_rows)

        rows.sort(key=lambda row: (row.code_femme, row.order))
        logger.info("%d avatars générés, %d profils en échec", len(rows), len(failures))
        return rows, failures
