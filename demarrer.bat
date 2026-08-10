@echo off
REM Demarrage en un double-clic (Windows).
REM Installe ce qu'il faut au premier lancement, puis ouvre l'application.

cd /d "%~dp0"
setlocal

echo.
echo   Palab Dossier Generator
echo   ------------------------
echo.

REM --- Verification des deux logiciels requis --------------------------------

where python >nul 2>&1
if errorlevel 1 (
  echo   Python n'est pas installe sur cet ordinateur.
  echo.
  echo   Installez-le depuis https://www.python.org/downloads/
  echo   IMPORTANT : cochez "Add Python to PATH" pendant l'installation.
  echo   Relancez ensuite ce fichier.
  echo.
  pause
  exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
  echo   Node.js n'est pas installe sur cet ordinateur.
  echo.
  echo   Installez-le depuis https://nodejs.org ^(bouton "LTS"^)
  echo   puis relancez ce fichier.
  echo.
  pause
  exit /b 1
)

REM --- Cle OpenAI : demandee une seule fois, stockee localement ---------------

REM Le prompt reste HORS d'un bloc entre parentheses : a l'interieur, cmd.exe
REM remplace %CLE% par sa valeur d'avant l'execution du bloc, donc toujours vide.

if exist .env goto cle_prete

echo   Premiere utilisation : votre cle OpenAI est necessaire.
echo   Elle reste sur cet ordinateur et n'est envoyee a personne d'autre qu'OpenAI.
echo.
set "CLE="
set /p CLE=  Collez votre cle puis appuyez sur Entree :
if not defined CLE goto pas_de_cle

copy .env.example .env >nul
python -c "import pathlib,sys;p=pathlib.Path('.env');p.write_text('\n'.join(('OPENAI_API_KEY='+sys.argv[1]) if l.startswith('OPENAI_API_KEY=') else l for l in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')" "%CLE%"
if errorlevel 1 goto cle_illisible
set "CLE="
echo.
echo   Cle enregistree. Elle ne vous sera plus redemandee.
echo.
goto cle_prete

:pas_de_cle
echo.
echo   Aucune cle saisie. Relancez ce fichier et collez votre cle.
echo   Astuce : dans cette fenetre, le collage se fait par un clic droit,
echo   pas par Ctrl+V, et la cle reste invisible pendant la frappe.
echo.
pause
exit /b 1

:cle_illisible
del .env >nul 2>&1
echo.
echo   La cle n'a pas pu etre enregistree. Relancez ce fichier.
echo.
pause
exit /b 1

:cle_prete

REM --- Installation, au premier lancement uniquement --------------------------

if not exist .venv (
  echo   Installation en cours. Comptez quelques minutes, une seule fois.
  echo.
  python -m venv .venv
  if errorlevel 1 goto echec
  .venv\Scripts\pip install --quiet --upgrade pip
  .venv\Scripts\pip install --quiet -r backend\requirements.txt
  if errorlevel 1 goto echec
  echo   Moteur installe.
)

if not exist frontend\node_modules (
  pushd frontend
  call npm install --silent
  if errorlevel 1 (popd & goto echec)
  popd
  echo   Interface installee.
  echo.
)

REM --- Aucune autre instance ne doit tourner ----------------------------------

python scripts\verifier_ports.py
if errorlevel 1 (
  pause
  exit /b 1
)

REM --- Demarrage --------------------------------------------------------------

REM Les sorties partent dans des fichiers : une fenetre minimisee qui se ferme
REM sur une erreur emporte sinon le seul message exploitable.
if not exist journaux mkdir journaux
start "Palab - moteur" /min cmd /c ".venv\Scripts\uvicorn backend.main:app --port 8000 > journaux\moteur.txt 2>&1"
start "Palab - interface" /min cmd /c "cd frontend && npm run dev > ..\journaux\interface.txt 2>&1"

echo   Demarrage...

REM L'adresse n'est pas garantie : si le port 3000 est deja pris, le serveur
REM bascule sur le suivant. On recupere donc l'adresse reellement utilisee.
set URL=
for /f "usebackq delims=" %%u in (`python scripts\attendre_app.py`) do set URL=%%u

if "%URL%"=="" (
  echo.
  echo   L'application n'a pas demarre.
  echo   Fermez cette fenetre, relancez ce fichier, et si le probleme persiste
  echo   signalez-le en recopiant ce qui s'affiche ici.
  echo.
  pause
  exit /b 1
)

start %URL%

echo.
echo   L'application est ouverte dans votre navigateur.
echo   Si l'onglet ne s'est pas ouvert : allez sur %URL%
echo.
echo   Gardez cette fenetre ouverte pendant que vous travaillez.
echo   Pour tout arreter : fermez cette fenetre et les deux fenetres "Palab".
echo.
echo   En cas de probleme, les messages du moteur sont dans le dossier
echo   "journaux", fichier moteur.txt.
echo.
pause
exit /b 0

:echec
echo.
echo   L'installation a echoue. Verifiez votre connexion Internet
echo   puis relancez ce fichier.
echo.
pause
exit /b 1
