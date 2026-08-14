# Palab Dossier Generator

Outil web qui remplit automatiquement un modèle Excel de collecte de profils :
génération des agents et des profils par l'API OpenAI en sortie structurée,
production d'avatars de synthèse, validation, puis export d'un classeur complété
et d'une archive ZIP.

Le classeur téléversé est la **source de vérité**. Aucune structure n'est codée en
dur : feuilles, en-têtes, formules, listes déroulantes et bornes de longueur sont
déduits du fichier à chaque téléversement, et le fichier d'origine n'est jamais
modifié.

---

## Deux façons de l'utiliser

**En ligne, sans rien installer** — voir [METTRE-EN-LIGNE.md](METTRE-EN-LIGNE.md).
Le dépôt contient un `render.yaml` : Render construit l'image, ne réclame que la
clé OpenAI et publie l'application à une adresse unique. C'est la voie
recommandée pour un usage non technique, et les mises à jour se déploient toutes
seules.

**En local** — voir [MODE-D-EMPLOI.md](MODE-D-EMPLOI.md) pour la version sans
jargon, ou les instructions ci-dessous.

En production, le serveur Python sert aussi l'interface compilée : une seule
adresse, un seul service, pas de configuration CORS.

## Installation

```bash
git clone <url-du-depot>
cd pipelinedossier
```

### Backend

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r backend/requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Configuration

Copiez `.env.example` vers `.env` à la racine, puis renseignez votre clé :

```env
OPENAI_API_KEY=sk-...
OPENAI_TEXT_MODEL=gpt-4.1-mini
OPENAI_IMAGE_MODEL=gpt-image-1
```

La clé reste côté serveur. Le frontend n'y a jamais accès : il appelle le backend,
qui appelle OpenAI. `.env` est exclu du dépôt par `.gitignore`.

`OPENAI_BASE_URL` permet de router vers une passerelle compatible OpenAI ; laissez
le champ vide pour utiliser l'API officielle.

## Lancement

Deux terminaux, depuis la racine du projet :

```bash
# Terminal 1 — backend
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

```bash
# Terminal 2 — frontend
cd frontend
npm run dev
```

Ouvrez ensuite <http://localhost:3000>.

### Docker (optionnel)

```bash
docker compose up --build
```

## Utilisation

1. Déposez `palabdossiercollecte.xlsx` dans la zone d'import.
2. Réglez le nombre de profils, d'agents, d'avatars, les pays et la tranche d'âge.
3. « Tester avec 3 profils » valide la chaîne sans consommer beaucoup de crédits.
4. « GÉNÉRER LE DOSSIER » lance la génération ; la progression s'affiche en direct.
5. Téléchargez le classeur ou l'archive ZIP complète.

L'onglet **Historique** liste les générations passées avec leurs téléchargements.

---

## Ce que le générateur ne fabrique pas

Le modèle décrit un circuit d'accueil de personnes réelles. Cinq colonnes n'y
enregistrent pas une donnée mais le fait qu'**un humain a vérifié un document** :

| Colonne | Traitement |
|---|---|
| Type de pièce d'identité | `N/A — démonstration` |
| Numéro de pièce | `N/A — démonstration` |
| Contrat de mandat signé | `N/A — démonstration` |
| Date de signature | `N/A — démonstration` |
| Consentement publication photos | `N/A — démonstration` |
| Statut du dossier | `À compléter` |

Les renseigner automatiquement pour un personnage inexistant produirait un
dossier indiscernable d'un dossier réellement contrôlé. Le « Lisez-moi » du modèle
prévoit ce cas : *« un dossier incomplet est importable, il restera simplement en
attente côté administration »*. Aucune pièce d'identité ni photo de vérification
de synthèse n'est produite.

Par ailleurs, tout dossier produit est marqué comme fictif :

- e-mails en `example.test` (domaine réservé, RFC 6761) et téléphones en `+99` ;
- `Notes internes` portant « PERSONNAGE FICTIF » sur chaque ligne ;
- avatars illustrés, non photographiques, avec provenance IA inscrite dans les
  métadonnées PNG ;
- `README.txt` inclus dans l'archive.

---

## Architecture

```
pipelinedossier/
├── backend/
│   ├── main.py                     point d'entrée FastAPI
│   ├── config.py                   configuration (.env)
│   ├── api/routes.py               routes HTTP + flux SSE
│   ├── core/logging.py             journalisation, masquage des secrets
│   ├── models/schemas.py           modèles Pydantic
│   ├── prompts/                    prompts, séparés de la logique métier
│   │   ├── profile_prompt.py
│   │   └── avatar_prompt.py
│   └── services/
│       ├── excel_introspect.py     analyse du modèle (lecture seule)
│       ├── field_policy.py         qui remplit quelle colonne
│       ├── openai_service.py       accès unique à l'API, réessais
│       ├── profile_generator.py    lots, schéma JSON, contrôle des longueurs
│       ├── image_generator.py      avatars, parallélisme borné
│       ├── excel_service.py        écriture sur copie du modèle
│       ├── validation_service.py   contrôles avant export
│       ├── zip_service.py          archive livrable
│       └── job_manager.py          orchestration, points de contrôle
├── frontend/src/
│   ├── App.tsx
│   ├── api.ts
│   └── components/
├── tests/
├── uploads/  outputs/  temp/
└── docker-compose.yml
```

### Points notables

**Introspection.** `excel_introspect.py` détecte la ligne d'en-tête réelle (celle
de `Femmes` est en ligne 2, sous une ligne de bandes fusionnées), repère la ligne
d'exemple à neutraliser, résout les listes déroulantes vers la feuille `Listes` et
lit les bornes de longueur **dans les formules de contrôle** — plus précises que
les en-têtes : l'en-tête « Accroche (120 caractères max) » tait le minimum de 40
que la formule impose.

**Formules.** Les formules du modèle sont recopiées vers les lignes ajoutées avec
réécriture des références de ligne, et les plages inter-feuilles sont réalignées
sur l'étendue réelle des données. Le `COUNTIF(Femmes!$B$4:$B$153)` de la feuille
`Agents` exclut la ligne d'exemple ; comme celle-ci redevient une ligne de
données, la borne descend à `$B$3` — sans quoi le premier profil ne serait pas
compté. Les listes déroulantes sont elles aussi prolongées au-delà des
151 lignes préparées par le modèle.

**Sortie structurée.** Le schéma JSON imposé au modèle est construit à partir des
colonnes détectées : listes déroulantes converties en `enum`, propriétés toutes
requises, `additionalProperties: false`. Les longueurs sont revérifiées côté
backend après génération ; un texte hors bornes est réécrit par le modèle, puis en
dernier recours coupé sur une frontière de phrase — jamais au milieu d'une idée.

**Coûts.** Les profils sont générés par lots (`PROFILE_BATCH_SIZE`, 10 par
défaut) et les images avec un parallélisme borné (`IMAGE_CONCURRENCY`).

**Reprise.** Chaque lot terminé est écrit sur disque. Un job interrompu se relance
via `POST /api/jobs/{job_id}/resume` (bouton « Reprendre » dans l'interface) et ne
régénère ni les profils déjà produits ni les avatars déjà présents.

## API

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/health` | état du serveur, présence de la clé (jamais sa valeur) |
| `POST` | `/api/upload` | téléverse et analyse le modèle |
| `POST` | `/api/jobs` | lance une génération |
| `POST` | `/api/jobs/{id}/resume` | reprend un job interrompu |
| `GET` | `/api/jobs/{id}` | état courant |
| `GET` | `/api/jobs/{id}/events` | progression en direct (SSE) |
| `GET` | `/api/jobs/{id}/report` | rapport de validation |
| `GET` | `/api/jobs/{id}/download/excel` | classeur complété |
| `GET` | `/api/jobs/{id}/download/zip` | archive complète |
| `GET` | `/api/history` | générations passées |

## Tests

```bash
# Tests unitaires (aucun appel réseau)
.venv/bin/python -m pytest tests/test_units.py -q
```

Les tests de bout en bout s'exécutent contre un serveur compatible OpenAI simulé,
qui permet d'exercer le vrai chemin du SDK sans consommer de crédits :

```bash
# Terminal 1
.venv/bin/python -m uvicorn tests.mock_openai_server:app --port 8899

# Terminal 2 — avec OPENAI_BASE_URL=http://127.0.0.1:8899/v1 dans .env
.venv/bin/python -m tests.run_e2e 3 2                  # pipeline complet
.venv/bin/python -m tests.verify_output outputs/JOB-…  # contrôle du classeur produit
.venv/bin/python -m tests.run_resume                   # reprise sur point de contrôle
```

`tests/verify_output.py` contrôle l'intégrité du classeur produit : feuilles,
en-têtes, cellules fusionnées, largeurs, listes déroulantes, présence des
formules sur toutes les lignes de données, réalignement des plages, colonnes de
vérification, longueurs de textes, correspondance exacte entre les noms de
fichiers de la feuille `Photos` et les images réellement présentes, validité du
ZIP, et intégrité du modèle source.
