"""Serveur compatible OpenAI, pour tester le pipeline sans consommer de crédits.

Il implémente le protocole réellement appelé par le SDK (`/v1/chat/completions`
avec sorties structurées, `/v1/images/generations`). Le code applicatif n'est
pas modifié ni contourné : seul `OPENAI_BASE_URL` change. Ce module vit sous
`tests/` et n'est jamais importé par le backend.

Lancement : python -m uvicorn tests.mock_openai_server:app --port 8899
"""

from __future__ import annotations

import base64
import json
import random
import re
import struct
import time
import zlib
from typing import Any

from fastapi import FastAPI, Request

app = FastAPI(title="Mock OpenAI")

# Trace des appels de retouche, pour vérifier le chaînage sur référence.
_EDIT_CALLS: list[dict[str, Any]] = []

PRENOMS = [
    "Aminata", "Fatou", "Adjoa", "Nadia", "Chantal", "Sylvie", "Mariam", "Rokia",
    "Grace", "Yasmine", "Awa", "Bintou", "Clarisse", "Fanta", "Kadiatou", "Leila",
    "Mireille", "Ngozi", "Oumou", "Salimata", "Thérèse", "Viviane", "Zeinab", "Aicha",
]
NOMS = [
    "Diallo", "Traoré", "Koné", "Ouédraogo", "Mensah", "Adjovi", "Bamba", "Cissé",
    "Diop", "Fall", "Gueye", "Kouassi", "Ndiaye", "Sow", "Touré", "Zongo",
]
VILLES = {
    "Bénin": ["Cotonou", "Porto-Novo", "Parakou"],
    "Côte d'Ivoire": ["Abidjan", "Bouaké", "Yamoussoukro"],
    "Sénégal": ["Dakar", "Thiès", "Saint-Louis"],
    "Togo": ["Lomé", "Sokodé", "Kara"],
    "Cameroun": ["Douala", "Yaoundé", "Bafoussam"],
    "Maroc": ["Casablanca", "Rabat", "Marrakech"],
}
GENTILES = {
    "Bénin": "Béninoise", "Côte d'Ivoire": "Ivoirienne", "Sénégal": "Sénégalaise",
    "Togo": "Togolaise", "Cameroun": "Camerounaise", "Maroc": "Marocaine",
}
PROFESSIONS = [
    "Infirmière", "Enseignante", "Comptable", "Couturière", "Coiffeuse",
    "Commerçante", "Secrétaire", "Sage-femme", "Vendeuse", "Restauratrice",
]
INTERETS = [
    "Cuisine", "Voyages", "Lecture", "Danse", "Musique", "Couture", "Jardinage",
    "Marche", "Cinéma", "Photographie", "Natation", "Bénévolat",
]

_LEN_RANGE = re.compile(r"entre (\d+) et (\d+) caract")
_LEN_MAX = re.compile(r"(\d+) caract[^\d]*maximum")
_FIX_RANGE = re.compile(r"Il doit en faire (?:entre (\d+) et (\d+)|au maximum (\d+))")
_COUNT = re.compile(r"Génère (\d+)")
_WINDOW = re.compile(r"comprise entre (\d{4}-\d{2}-\d{2}) et (\d{4}-\d{2}-\d{2})")
_COUNTRIES = re.compile(r"répartir parmi : ([^\n]+)")


def _filler(target: int, seed: int) -> str:
    """Texte français de longueur ~target, terminé par une phrase complète."""
    rng = random.Random(seed)
    phrases = [
        "J'aime les journées simples et les gens sincères",
        "Je travaille beaucoup mais je garde du temps pour les miens",
        "Le week-end je retrouve ma famille et je cuisine",
        "J'ai appris à avancer sans me presser",
        "Je crois qu'on se construit avec de la patience",
        "Mes amies disent que je suis discrète mais fidèle",
        "J'aime marcher le soir quand la ville se calme",
        "Je lis un peu chaque jour avant de dormir",
        "Ce qui compte pour moi c'est la confiance",
        "Je préfère les échanges vrais aux grands discours",
    ]
    out: list[str] = []
    length = 0
    while length < target - 20:
        phrase = phrases[rng.randrange(len(phrases))]
        out.append(phrase)
        length += len(phrase) + 2
    text = ". ".join(out) + "."
    if len(text) > target:
        cut = text.rfind(". ", 0, target - 1)
        text = text[: cut + 1] if cut > target * 0.5 else text[: target - 1] + "."
    return text


def _value_for(name: str, spec: dict[str, Any], ctx: dict[str, Any], rng: random.Random) -> Any:
    if "enum" in spec:
        return rng.choice(spec["enum"])

    description = spec.get("description", "")
    if spec.get("type") == "integer":
        bounds = {
            "taille_cm": (150, 180), "poids_kg": (50, 80),
            "age_recherche_min": (25, 35), "age_recherche_max": (45, 60),
        }
        low, high = bounds.get(name, (1, 10))
        return rng.randint(low, high)

    match name:
        case "nom_legal_complet":
            return f"{ctx['prenom']} {rng.choice(NOMS)} {rng.choice(NOMS)}"
        case "prenom_affiche":
            return ctx["prenom"]
        case "date_naissance":
            return ctx["birth"]
        case "nationalite":
            return GENTILES.get(ctx["pays"], "Ivoirienne")
        case "pays_residence" | "pays_affiche":
            return ctx["pays"]
        case "ville_residence" | "ville_affichee":
            return ctx["ville"]
        case "profession":
            return ctx["profession"]
        case "langues":
            return "Français: natif ; Anglais: intermédiaire"
        case "centres_interet":
            return " ; ".join(rng.sample(INTERETS, 4))
        case "nom_agence":
            return f"Agence {rng.choice(['Horizon', 'Sahel', 'Atlantique', 'Baobab', 'Lagune'])} {ctx['index']}"
        case "personne_responsable":
            return f"Mme {rng.choice(PRENOMS)} {rng.choice(NOMS)}"
        case "pays":
            return ctx["pays"]
        case "ville":
            return ctx["ville"]

    ranged = _LEN_RANGE.search(description)
    if ranged:
        low, high = int(ranged.group(1)), int(ranged.group(2))
        return _filler((low + high) // 2, rng.randrange(10_000))
    capped = _LEN_MAX.search(description)
    if capped:
        return _filler(int(int(capped.group(1)) * 0.8), rng.randrange(10_000))
    return f"{name} fictif {ctx['index']}"


def _build_items(schema: dict[str, Any], prompt: str, count: int) -> list[dict[str, Any]]:
    root_key = next(iter(schema["properties"]))
    item_schema = schema["properties"][root_key]["items"]
    properties: dict[str, Any] = item_schema["properties"]

    countries_match = _COUNTRIES.search(prompt)
    countries = (
        [c.strip() for c in countries_match.group(1).split(",")]
        if countries_match
        else list(VILLES)
    )
    window = _WINDOW.search(prompt)
    start = window.group(1) if window else "1985-01-01"

    rng = random.Random(len(prompt))
    items: list[dict[str, Any]] = []
    for index in range(count):
        pays = countries[index % len(countries)]
        ctx = {
            "index": index + 1,
            "pays": pays,
            "ville": rng.choice(VILLES.get(pays, ["Abidjan"])),
            "prenom": PRENOMS[(index + rng.randrange(3)) % len(PRENOMS)],
            "profession": PROFESSIONS[index % len(PROFESSIONS)],
            "birth": f"{int(start[:4]) + (index % 6)}-0{(index % 9) + 1}-1{index % 9}",
        }
        items.append({name: _value_for(name, spec, ctx, rng) for name, spec in properties.items()})
    return items


def _solid_png(width: int = 96, height: int = 128, seed: int = 0) -> bytes:
    rng = random.Random(seed)
    r, g, b = rng.randrange(90, 220), rng.randrange(90, 220), rng.randrange(90, 220)
    raw = b"".join(b"\x00" + bytes([r, g, b]) * width for _ in range(height))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict[str, Any]:
    body = await request.json()
    prompt = "\n".join(m.get("content", "") for m in body.get("messages", []))
    response_format = body.get("response_format") or {}

    if response_format.get("type") == "json_schema":
        schema = response_format["json_schema"]["schema"]
        count_match = _COUNT.search(prompt)
        count = int(count_match.group(1)) if count_match else 1
        root_key = next(iter(schema["properties"]))
        content = json.dumps({root_key: _build_items(schema, prompt, count)}, ensure_ascii=False)
    else:
        bounds = _FIX_RANGE.search(prompt)
        if bounds and bounds.group(1):
            target = (int(bounds.group(1)) + int(bounds.group(2))) // 2
        elif bounds:
            target = int(int(bounds.group(3)) * 0.85)
        else:
            target = 200
        content = _filler(target, len(prompt))

    return {
        "id": "chatcmpl-mock", "object": "chat.completion", "created": int(time.time()),
        "model": body.get("model", "mock"),
        "choices": [{
            "index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": content},
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.post("/v1/images/edits")
async def images_edits(request: Request) -> dict[str, Any]:
    """Retouche depuis une image de référence, servie en multipart."""
    form = await request.form()
    prompt = str(form.get("prompt", ""))
    uploads = form.getlist("image[]") or form.getlist("image")
    _EDIT_CALLS.append({"prompt": prompt, "references": len(uploads)})
    png = _solid_png(seed=len(prompt))
    return {
        "created": int(time.time()),
        "data": [{"b64_json": base64.b64encode(png).decode("ascii")}],
    }


@app.get("/_calls/edits")
async def edit_calls() -> dict[str, Any]:
    """Introspection de test : combien de retouches, avec quels prompts."""
    return {"count": len(_EDIT_CALLS), "calls": _EDIT_CALLS}


@app.post("/v1/images/generations")
async def images_generations(request: Request) -> dict[str, Any]:
    body = await request.json()
    png = _solid_png(seed=len(body.get("prompt", "")))
    return {
        "created": int(time.time()),
        "data": [{"b64_json": base64.b64encode(png).decode("ascii")}],
    }
