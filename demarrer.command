#!/bin/bash
# Démarrage en un double-clic (macOS et Linux).
# Installe ce qu'il faut au premier lancement, puis ouvre l'application.

cd "$(dirname "$0")" || exit 1

RED=$'\033[31m'; GREEN=$'\033[32m'; BOLD=$'\033[1m'; OFF=$'\033[0m'

echo ""
echo "${BOLD}  Palab Dossier Generator${OFF}"
echo "  ------------------------"
echo ""

fatal() {
  echo ""
  echo "${RED}  $1${OFF}"
  echo ""
  echo "  $2"
  echo ""
  echo "  Appuyez sur Entrée pour fermer."
  read -r
  exit 1
}

# --- Vérification des deux logiciels requis ---------------------------------

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  fatal "Python n'est pas installé sur cet ordinateur." \
        "Installez-le depuis https://www.python.org/downloads/ puis relancez ce fichier."
fi

if ! command -v node >/dev/null 2>&1; then
  fatal "Node.js n'est pas installé sur cet ordinateur." \
        "Installez-le depuis https://nodejs.org (bouton « LTS ») puis relancez ce fichier."
fi

# --- Clé OpenAI : demandée une seule fois, stockée localement ----------------

if [ ! -f .env ]; then
  echo "  Première utilisation : votre clé OpenAI est nécessaire."
  echo "  Elle reste sur cet ordinateur et n'est envoyée à personne d'autre qu'OpenAI."
  echo ""
  printf "  Collez votre clé puis appuyez sur Entrée : "
  read -r CLE
  if [ -z "$CLE" ]; then
    fatal "Aucune clé saisie." "Relancez ce fichier et collez votre clé."
  fi
  cp .env.example .env
  # Remplace la ligne de la clé sans toucher au reste du fichier.
  "$PY" - "$CLE" <<'PYEOF'
import pathlib, sys
path = pathlib.Path(".env")
lines = path.read_text(encoding="utf-8").splitlines()
out = [f"OPENAI_API_KEY={sys.argv[1]}" if l.startswith("OPENAI_API_KEY=") else l for l in lines]
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PYEOF
  echo ""
  echo "${GREEN}  Clé enregistrée.${OFF} Elle ne vous sera plus redemandée."
  echo ""
fi

# --- Installation, au premier lancement uniquement --------------------------

if [ ! -d .venv ]; then
  echo "  Installation en cours. Comptez quelques minutes, une seule fois."
  echo ""
  "$PY" -m venv .venv || fatal "L'installation a échoué." "Vérifiez votre connexion Internet."
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r backend/requirements.txt \
    || fatal "L'installation a échoué." "Vérifiez votre connexion Internet."
  echo "${GREEN}  Moteur installé.${OFF}"
fi

if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install --silent) \
    || fatal "L'installation a échoué." "Vérifiez votre connexion Internet."
  echo "${GREEN}  Interface installée.${OFF}"
  echo ""
fi

# --- Démarrage ---------------------------------------------------------------

arreter() {
  echo ""
  echo "  Arrêt de l'application."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  exit 0
}
trap arreter INT TERM

./.venv/bin/uvicorn backend.main:app --port 8000 --log-level warning &
BACKEND_PID=$!

(cd frontend && npm run dev --silent) &
FRONTEND_PID=$!

echo "  Démarrage…"
for _ in $(seq 1 40); do
  if curl -s -o /dev/null http://localhost:3000/ 2>/dev/null; then break; fi
  sleep 0.5
done

if command -v open >/dev/null 2>&1; then
  open http://localhost:3000
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open http://localhost:3000 >/dev/null 2>&1
fi

echo ""
echo "${GREEN}${BOLD}  L'application est ouverte dans votre navigateur.${OFF}"
echo "  Si l'onglet ne s'est pas ouvert : allez sur http://localhost:3000"
echo ""
echo "  ${BOLD}Gardez cette fenêtre ouverte${OFF} pendant que vous travaillez."
echo "  Pour tout arrêter : fermez cette fenêtre."
echo ""

wait
