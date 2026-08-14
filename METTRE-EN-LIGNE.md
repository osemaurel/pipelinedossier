# Mettre l'outil en ligne

Pour obtenir **une adresse internet** sur laquelle cliquer, sans rien installer
sur votre ordinateur. Une fois fait, l'outil est accessible depuis n'importe quel
appareil, y compris votre téléphone.

Comptez un quart d'heure la première fois. Ensuite, il n'y a plus jamais rien à
refaire : vous ouvrez le lien, c'est tout.

---

## Ce qu'il vous faut

- Un compte **GitHub** — vous en avez déjà un, c'est là qu'est le projet.
- Un compte **Render** — gratuit à créer, sur <https://render.com>.
- Votre clé OpenAI.

---

## Les étapes

### 1. Créer le compte Render

Allez sur <https://render.com>, cliquez sur **Get Started**, puis choisissez
**Sign in with GitHub**. Autorisez Render à accéder à vos dépôts quand il le
demande. C'est ce qui lui permettra de récupérer le code tout seul.

### 2. Lancer le déploiement

Dans le tableau de bord Render :

1. Bouton **New +** en haut à droite
2. Choisissez **Blueprint**
3. Dans la liste, sélectionnez le dépôt **pipelinedossier**
4. Render affiche « palab-dossier-generator ». Cliquez sur **Apply** ou
   **Deploy**.

Render lit le fichier `render.yaml` du projet et sait déjà tout construire. Vous
n'avez aucun réglage technique à faire.

### 3. Donner votre clé

Render vous réclame une seule valeur : **OPENAI_API_KEY**.

Collez votre clé dans le champ, validez.

Elle est stockée côté serveur, chiffrée. Elle n'apparaît jamais dans le
navigateur ni dans le code.

### 4. Attendre la construction

Render fabrique l'application. **Comptez cinq à dix minutes la première fois.**
Vous voyez du texte défiler — c'est normal, laissez faire.

Quand c'est terminé, le statut passe à **Live** et votre adresse s'affiche en
haut, du type :

```
https://palab-dossier-generator.onrender.com
```

**C'est votre lien.** Mettez-le en favori.

### 5. Utiliser

Ouvrez le lien. Vous retrouvez exactement l'application, en mieux : plus de
fenêtre noire, plus de fichier `.env`, plus de version périmée possible.

Déposez votre fichier Excel, réglez ce que vous voulez, cliquez sur
**Tester avec 3 profils**.

---

## Quand je publie une correction

Render suit automatiquement le dépôt : **dès que je pousse une correction, votre
site se met à jour tout seul** en quelques minutes. Vous n'avez plus jamais à
retélécharger quoi que ce soit.

C'est le principal avantage par rapport à l'installation sur votre ordinateur.

---

## À savoir

**Le coût.** Le fichier de configuration demande le plan **Starter** (environ
7 $ par mois). C'est volontaire : le plan gratuit met le service en veille au
bout d'un quart d'heure sans visite et coupe les traitements longs — une
génération de 50 profils n'irait pas au bout. Si vous voulez essayer en gratuit
d'abord, changez `plan: starter` en `plan: free` dans `render.yaml`, ou
choisissez Free dans l'interface de Render.

**Les fichiers produits.** Le service dispose d'un disque persistant de 5 Go :
vos dossiers survivent aux redémarrages et aux mises à jour, et restent
téléchargeables depuis l'onglet **Historique**. Pensez tout de même à récupérer
vos ZIP, le disque n'est pas infini.

**Pendant une mise à jour.** Quand je pousse une correction, Render reconstruit
le service : il est indisponible deux à trois minutes et les requêtes échouent.
Attendez le retour du statut **Live**, rechargez la page, et reprenez.

**Le coût des images** reste facturé par OpenAI, sur votre compte, comme avant.
Render héberge, OpenAI génère.

---

## Si ça bloque

Dans Render, onglet **Logs** du service : les erreurs s'y affichent en clair.
Copiez le message et envoyez-le moi.

**Ne copiez jamais la ligne contenant votre clé** — elle commence par `sk-`.
