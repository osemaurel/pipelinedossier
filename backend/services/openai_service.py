"""Point d'accès unique à l'API OpenAI.

Toute la configuration (clé, modèles, URL de base, délais, réessais) est
centralisée ici. Aucun autre module ne construit de client OpenAI, et la clé ne
quitte jamais le serveur.

L'API Chat Completions est retenue plutôt que l'API Responses parce que
`OPENAI_BASE_URL` permet de router vers une passerelle compatible OpenAI : les
sorties structurées en Chat Completions sont le dénominateur commun de ces
passerelles.
"""

from __future__ import annotations

import asyncio
import base64
import json
import random
from typing import Any

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from backend.config import Settings, get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

RETRYABLE = (RateLimitError, APIConnectionError)


class OpenAIConfigurationError(RuntimeError):
    pass


class OpenAIService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.openai_api_key:
            raise OpenAIConfigurationError(
                "OPENAI_API_KEY absente. Renseignez-la dans le fichier .env du serveur."
            )
        self._client = AsyncOpenAI(
            api_key=self._settings.openai_api_key,
            base_url=self._settings.openai_base_url or None,
            timeout=self._settings.request_timeout,
            max_retries=0,  # les réessais sont gérés ici, avec journalisation
        )

    @property
    def text_model(self) -> str:
        return self._settings.openai_text_model

    @property
    def image_model(self) -> str:
        return self._settings.openai_image_model

    async def _with_retries(self, label: str, operation: Any) -> Any:
        last: Exception | None = None
        for attempt in range(1, self._settings.max_retries + 1):
            try:
                return await operation()
            except RETRYABLE as exc:
                last = exc
                delay = min(2 ** attempt, 30) + random.uniform(0, 0.75)
                logger.warning(
                    "%s : tentative %d/%d échouée (%s). Nouvel essai dans %.1fs.",
                    label, attempt, self._settings.max_retries, type(exc).__name__, delay,
                )
                await asyncio.sleep(delay)
            except APIStatusError as exc:
                if exc.status_code and 500 <= exc.status_code < 600:
                    last = exc
                    delay = min(2 ** attempt, 30) + random.uniform(0, 0.75)
                    logger.warning(
                        "%s : erreur serveur %s (tentative %d/%d). Nouvel essai dans %.1fs.",
                        label, exc.status_code, attempt, self._settings.max_retries, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
        assert last is not None
        raise last

    async def structured_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        json_schema: dict[str, Any],
        temperature: float = 0.9,
    ) -> dict[str, Any]:
        """Appel texte en sortie structurée. Le schéma est imposé au modèle."""

        async def call() -> Any:
            return await self._client.chat.completions.create(
                model=self.text_model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "strict": True,
                        "schema": json_schema,
                    },
                },
            )

        response = await self._with_retries(f"génération « {schema_name} »", call)
        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise RuntimeError(
                f"Réponse tronquée pour « {schema_name} » : réduisez la taille des lots."
            )
        content = choice.message.content or ""
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Réponse JSON illisible pour « {schema_name} » : {exc}") from exc

    async def plain_text(
        self, *, system_prompt: str, user_prompt: str, temperature: float = 0.5
    ) -> str:
        async def call() -> Any:
            return await self._client.chat.completions.create(
                model=self.text_model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

        response = await self._with_retries("réécriture de texte", call)
        return (response.choices[0].message.content or "").strip()

    async def image_png(self, prompt: str) -> bytes:
        """Génère une image et renvoie ses octets PNG."""

        async def call() -> Any:
            return await self._client.images.generate(
                model=self.image_model,
                prompt=prompt,
                size=self._settings.openai_image_size,
                n=1,
            )

        response = await self._with_retries("génération d'image", call)
        item = response.data[0]
        payload = getattr(item, "b64_json", None)
        if payload:
            return base64.b64decode(payload)
        url = getattr(item, "url", None)
        if not url:
            raise RuntimeError("Réponse image sans contenu exploitable.")
        import httpx

        async with httpx.AsyncClient(timeout=self._settings.request_timeout) as client:
            downloaded = await client.get(url)
            downloaded.raise_for_status()
            return downloaded.content
