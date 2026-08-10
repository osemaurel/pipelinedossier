# Mode d'emploi

Notice pour utiliser l'outil sans rien connaître à la programmation.

---

## Ce qu'il faut installer une fois

Deux logiciels gratuits. Vous ne les ouvrirez jamais : ils font tourner
l'application en coulisses.

**1. Python** — <https://www.python.org/downloads/>
Cliquez sur le gros bouton jaune, ouvrez le fichier téléchargé, suivez les
étapes.
*Sur Windows* : à la première fenêtre, cochez la case **« Add Python to PATH »**
en bas avant de cliquer sur Install. C'est important.

**2. Node.js** — <https://nodejs.org>
Cliquez sur le bouton **LTS** (celui de gauche), ouvrez le fichier téléchargé,
suivez les étapes en laissant tout par défaut.

Redémarrez votre ordinateur après ces deux installations.

---

## Récupérer l'outil

Sur la page du projet sur GitHub, bouton vert **« Code »**, puis
**« Download ZIP »**. Décompressez le dossier téléchargé et posez-le où vous
voulez — par exemple sur le Bureau.

---

## Lancer l'outil

Ouvrez le dossier et double-cliquez sur :

- **`demarrer.command`** si vous êtes sur Mac
- **`demarrer.bat`** si vous êtes sur Windows

Une fenêtre noire s'ouvre. C'est normal, c'est le moteur : **laissez-la ouverte**.

**La toute première fois**, elle vous demande votre clé OpenAI. Collez-la,
appuyez sur Entrée. Elle ne vous sera plus jamais redemandée : elle est
enregistrée sur votre ordinateur et n'est envoyée à personne d'autre qu'OpenAI.

Ensuite l'installation se fait toute seule. **Comptez cinq à dix minutes la
première fois**, c'est long et c'est normal. Les fois suivantes, le démarrage
prend quelques secondes.

Votre navigateur s'ouvre alors sur l'application. S'il ne s'ouvre pas tout seul,
tapez cette adresse dans votre navigateur : **http://localhost:3000**

---

### Sur Mac, si un message dit que le fichier n'est pas autorisé

macOS bloque par défaut les fichiers téléchargés. Faites un **clic droit** sur
`demarrer.command` → **Ouvrir** → puis **Ouvrir** à nouveau dans la fenêtre qui
apparaît. À faire une seule fois.

---

## Utiliser l'outil

1. Glissez votre fichier `palabdossiercollecte.xlsx` dans le cadre en pointillés.
2. Réglez ce que vous voulez : nombre de profils, pays, âges, nombre d'images.
3. **Commencez toujours par le bouton « Tester avec 3 profils ».** Il vérifie que
   tout marche pour quelques centimes, avant de lancer une grosse génération.
4. Si le test réussit, cliquez sur **« GÉNÉRER LE DOSSIER »**.
5. À la fin, deux boutons apparaissent pour télécharger le résultat.

L'onglet **Historique**, en haut à droite, garde la trace de vos générations
précédentes et permet de les retélécharger.

---

## Arrêter l'outil

Fermez la fenêtre noire. C'est tout.
*Sur Windows*, fermez aussi les deux petites fenêtres nommées « Palab ».

---

## Si quelque chose ne va pas

**« Python n'est pas installé »** ou **« Node.js n'est pas installé »**
Ces logiciels ne sont pas installés, ou vous n'avez pas redémarré l'ordinateur
après les avoir installés. Sur Windows, c'est souvent la case
« Add Python to PATH » qui a été oubliée : réinstallez Python en la cochant.

**« insufficient_quota » ou une erreur parlant de quota**
Votre compte OpenAI n'a plus de crédit. Rechargez-le sur
<https://platform.openai.com> → Billing.

**« invalid_api_key »**
La clé a été mal copiée. Supprimez le fichier nommé `.env` dans le dossier, puis
relancez : la clé vous sera redemandée.

**« Aucune clé saisie » alors que vous l'avez bien collée**
Dans la fenêtre noire de Windows, le collage se fait par un **clic droit**, pas
par Ctrl+V, et **la clé reste invisible pendant que vous la collez** — c'est
normal, tapez Entrée quand même.

Si le problème persiste, enregistrez la clé vous-même, c'est très simple :

1. Dans le dossier, faites une copie du fichier `.env.example`.
2. Renommez cette copie en `.env` — exactement ça, un point puis `env`, sans
   rien après.
3. Ouvrez-la avec le Bloc-notes (clic droit → Ouvrir avec → Bloc-notes).
4. Sur la ligne `OPENAI_API_KEY=`, collez votre clé juste après le `=`, sans
   espace. Vous devez obtenir quelque chose comme
   `OPENAI_API_KEY=sk-proj-abc123...`
5. Enregistrez, fermez, relancez `demarrer.bat`.

*Windows masque parfois les extensions* : si vous voyez `.env.txt` au lieu de
`.env`, allez dans l'onglet Affichage de l'explorateur et cochez « Extensions de
noms de fichiers » pour pouvoir corriger le nom.

**La page reste blanche**
Attendez une minute — au premier lancement, le démarrage est lent. Puis
actualisez la page.

Pour toute autre erreur, recopiez le message affiché dans la fenêtre noire.
**Ne recopiez jamais votre clé** : elle commence par `sk-` et ne doit être
partagée avec personne.
