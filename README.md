# Recherche immobilière : Luxembourg et zone frontalière (version 1)

Une application personnelle qui lit vos alertes e-mail (atHome, Immotop, Wortimmo…), en tire les annonces, retire les doublons, calcule le coût total réel et le temps de trajet jusqu'à Leudelange, puis classe les biens selon vos critères.

## 1. Comment ça marche

```
 Sites immobiliers ──(alertes e-mail)──► Boîte Gmail         
                                              │  lecture (IMAP)         
                                              ▼
                     ┌──────────── Application (sur votre PC Windows) ────────────┐
                     │ 1. extraction des annonces dans les e-mails                │
                     │ 2. suppression des doublons (même bien sur plusieurs sites) │
                     │ 3. position de la commune + distance à la frontière         │
                     │ 4. trajets voiture (OpenRouteService) et transports         │
                     │    (mobiliteit.lu)                                          │
                     │ 5. frais (barèmes LU / FR / BE, Bëllegen Akt) et score      │
                     │ 6. base locale SQLite : data/immo.db                        │
                     └───────────────────────────┬────────────────────────────────┘
                                                 ▼
                      Navigateur : PC (localhost:5000) ou téléphone (même Wi-Fi)
```

- **Aucun aspiration (scraping) des sites** : l'application lit seulement les e-mails que vous recevez.
- **Tout reste chez vous** : la base de données est un simple fichier, `data/immo.db`.
- **Clés et mots de passe** : uniquement dans le fichier `.env`, jamais dans le code.

## 2. Démarrage rapide (sans aucun compte)

1. Placez le dossier `recherche-immo` dans un chemin court, par exemple `C:\immo`. Windows gère mal les chemins très longs.
2. Double-cliquez sur **`lancer.bat`**. La première fois, l'installation prend 1 à 2 minutes.
3. Le navigateur s'ouvre sur http://localhost:5000.
4. Allez dans **Import**, puis cliquez sur **Charger la démo** : 7 annonces fictives apparaissent.
5. Quand vous avez fini de regarder, cliquez sur **Supprimer les biens de démo**.

Pour l'ouvrir sur votre téléphone, connectez le Samsung au même Wi-Fi que le PC et ouvrez l'adresse affichée dans la fenêtre noire, par exemple `http://192.168.1.20:5000`. Windows peut vous demander d'autoriser Python sur le réseau : répondez **Réseau privé** uniquement.

> L'application ne fonctionne que lorsque le PC est allumé et que la fenêtre noire est ouverte.

## 3. Ce que vous devez préparer

Chaque étape est **gratuite** et **facultative** : l'application marche déjà sans, mais elle est moins complète.

| # | Quoi | Pourquoi | Coût |
|---|------|----------|------|
| A | Alertes sur atHome.lu, Immotop.lu, Wortimmo.lu (et éventuellement SeLoger/Leboncoin pour la France, Immoweb pour la Belgique), reçues dans Gmail | La source des annonces | Gratuit |
| B | Un « mot de passe d'application » Gmail (5 minutes) | Lire les alertes dans Gmail | Gratuit |
| C | Clé OpenRouteService | Vrais temps de trajet en voiture + position plus précise | Gratuit, 2 000 calculs/jour |
| D | Clé API mobiliteit.lu | Temps de trajet en transports en commun | Gratuit, sur demande par e-mail |
| E | (facultatif) Mot de passe de l'application | Protéger l'accès depuis le Wi-Fi | — |

### A. Les alertes e-mail
Critères à saisir sur chaque site : **vente**, maison + appartement, prix maximum **500 000 €**, au moins 1 chambre, tout le Luxembourg. Pour la France et la Belgique, ajoutez les communes frontalières (Audun-le-Tiche, Villerupt, Longwy, Hettange-Grande, Arlon, Aubange, Messancy…). Choisissez une fréquence **quotidienne** ou **immédiate**, et votre adresse **Gmail**.
Si des alertes arrivent déjà sur Hotmail, faites-les suivre vers Gmail : sur outlook.live.com, ⚙️ Paramètres → Courrier → Règles → Ajouter une règle ; condition **De** = athome.lu, immotop.lu, wortimmo.lu ; action **Transférer à** = votre Gmail.
Gardez des filtres larges : l'application fait elle-même le tri fin (plain-pied, RDC, 50 m², garage, trajet).

### B. Lire Gmail : le mot de passe d'application (méthode recommandée)
1. Sur https://myaccount.google.com → **Sécurité**, activez la **Validation en deux étapes**.
2. Sur https://myaccount.google.com/apppasswords, créez un mot de passe nommé `immo` et copiez les 16 lettres.
3. Dans `.env`, remplissez :
   ```
   IMAP_HOST=imap.gmail.com
   IMAP_USER=votre.adresse@gmail.com
   IMAP_PASSWORD=les16lettressansespaces
   IMAP_FOLDER=INBOX
   ```
4. Relancez `lancer.bat`. La page **Import** doit afficher « ✅ IMAP : configuré ».

Ce mot de passe ne sert qu'à l'application ; vous pouvez le supprimer à tout moment sur la même page Google.

### B bis. (Ne fonctionne pas avec un compte Microsoft personnel) Lire Hotmail via une application Microsoft
Microsoft refuse en général cette inscription pour un compte personnel (erreur « does not exist in tenant 'Microsoft Services' »). Cette méthode n'est gardée que pour un compte professionnel :
1. Allez sur https://entra.microsoft.com et connectez-vous avec votre compte Microsoft (Hotmail).
2. Ouvrez **Applications → Inscriptions d'applications → Nouvelle inscription**.
   - Nom : `Recherche immo`
   - Types de comptes : **Comptes Microsoft personnels uniquement**
   - Laissez « URI de redirection » vide, puis cliquez sur **S'inscrire**.
3. Copiez **l'ID d'application (client)** et collez-le dans `.env` après `MS_CLIENT_ID=`.
4. Dans **Authentification**, mettez « Autoriser les flux de clients publics » sur **Oui**, puis enregistrez.
5. Dans **Autorisations d'API → Ajouter → Microsoft Graph → Autorisations déléguées**, cochez **Mail.Read**.
6. Relancez l'application. Dans **Import**, cliquez sur **Connecter Outlook**, puis tapez le code affiché sur microsoft.com/devicelogin.

L'application ne peut que **lire** vos e-mails. Elle ne traite que ceux des expéditeurs immobiliers listés dans Paramètres.

### C. OpenRouteService (voiture)
Inscrivez-vous sur https://openrouteservice.org/dev/#/signup, copiez la clé (« API Key ») et collez-la après `ORS_API_KEY=`.
Comme le service ne connaît pas les bouchons, l'application ajoute **+25 %** pour l'heure de pointe. Ce pourcentage se règle dans Paramètres.

### D. mobiliteit.lu (transports en commun)
L'API des transports publics luxembourgeois (horaires des bus et trains, y compris transfrontaliers) est gratuite, mais la clé se demande par e-mail. Les instructions sont sur https://data.public.lu (cherchez « API mobiliteit.lu »). Collez la clé reçue après `MOBILITEIT_API_KEY=`.
En attendant, vous pouvez saisir le temps de transport à la main sur chaque fiche ; le bouton « Vérifier l'itinéraire » ouvre Google Maps.

Pour modifier `.env`, faites un clic droit dessus, puis **Ouvrir avec → Bloc-notes**. Enregistrez, puis relancez `lancer.bat`.

## 4. Utilisation

- **Biens** : la liste est triée par score. Vous pouvez filtrer par pays, commune, prix, prix au m², surface, chambres, garage ou trajet. Les biens à 2 chambres sont repérés par une barre verte. Les biens hors critères sont masqués ; une case permet de les afficher.
- **Fiche** : on y trouve le résumé, les trajets, le détail des frais et du coût total, le détail du score et les liens vers les annonces. Comme les alertes ne contiennent pas tout, le formulaire en bas de fiche permet de **corriger ou compléter** la fiche. Une correction n'est jamais écrasée par un import.
- **Import** : lancement manuel, connexion Outlook, mode démo et journal. L'import se fait aussi **automatiquement toutes les 4 heures** tant que l'application est ouverte.
- **Paramètres** : tous les critères, les barèmes de frais (Bëllegen Akt à vérifier chaque année sur guichet.lu), les poids du score et l'adresse du travail.

## 4 bis. Sur le téléphone, partout (Tailscale)

- **Démarrage automatique** : l'application se lance seule, sans fenêtre, à chaque ouverture de session Windows (raccourci « Recherche immo » dans le dossier Démarrage). Journal : `data/app.log`. Pour retirer : `installer_demarrage_auto.bat retirer`.
- **Accès à distance** : Tailscale (gratuit) relie le PC et le téléphone par un réseau privé chiffré. L'application est publiée uniquement dans ce réseau privé, à l'adresse **https://&lt;nom-du-PC&gt;.&lt;réseau&gt;.ts.net** affichée par Tailscale (commande : `tailscale serve --bg 5000`). Rien n'est ouvert sur Internet.

## 4 ter. Version en ligne, sans le PC (consultation seule)

- **Principe** : GitHub (gratuit) fait tourner l'import toutes les 2 heures, même PC éteint, puis publie une page de consultation sur GitHub Pages (fichier `.github/workflows/mise-a-jour.yml`).
- **Confidentialité** : le code est public, mais il ne contient ni clé ni donnée personnelle. Les annonces et la base sont **chiffrées** (AES-256) avec le mot de passe `SITE_PASSWORD`. Sans ce mot de passe, la page en ligne est illisible.
- **Secrets GitHub** (Settings → Secrets and variables → Actions) : `IMAP_USER`, `IMAP_PASSWORD`, `ORS_API_KEY`, `SITE_PASSWORD`. Le script `publier_secrets.bat` les copie depuis `.env`.
- **Limites** : pas de correction de fiche ni de réglage depuis cette version. Une correction faite sur le PC n'est pas reportée en ligne.
- **À la main** : `python exporter_site.py` fabrique le site dans `site/`. `python -m immo.chiffrement dechiffrer|chiffrer` (dé)chiffre la base.
- **Sur le téléphone** : application Tailscale (Play Store), connectée au même compte Google ; puis ouvrir l'adresse ci-dessus dans Chrome → menu ⋮ → **Installer l'application** (ou « Ajouter à l'écran d'accueil »).
- **Limite** : le PC doit être allumé (pas en veille).

## 5. Limites connues de la version 1

- Les alertes indiquent rarement l'adresse exacte. Le bien est donc placé **au centre de sa commune**.
- La reconnaissance des e-mails repose sur des règles générales. Si un site change sa mise en page, certains champs peuvent rester vides : corrigez-les sur la fiche, ou envoyez-moi un exemple d'e-mail (.eml) pour que j'adapte l'extraction.
- La frontière luxembourgeoise est un tracé simplifié, précis à 1 ou 2 km près.
- Les frais sont des estimations. Pour un bien neuf vendu sur plan au Luxembourg, les droits ne portent en réalité que sur le terrain : le calcul est donc prudent.

## 6. Prochaines versions

- **V2** : carte des biens, favoris, notes, statuts (à visiter / visité / écarté) et **notifications sur le téléphone**. Je recommande **ntfy** : une application Android gratuite, sans compte, qui reçoit une notification dès qu'un bien bien noté arrive. C'est plus simple et plus fiable qu'une PWA, qui exigerait un hébergement HTTPS. Pour consulter l'application hors de chez vous, **Tailscale** (gratuit) suffira.
- **V3** : terrains à bâtir, annuaire comparatif des constructeurs de maisons préfabriquées et simulateur terrain + maison + raccordements + frais (avec un rappel sur le PAG et le permis de bâtir).

## 7. Pour les curieux (technique)

Python 3 + Flask, SQLite et des pages HTML générées côté serveur, sans framework JavaScript.

| Fichier | Rôle |
|---|---|
| `app.py` | pages web et import automatique en tâche de fond |
| `immo/boite_mail.py` | lecture des e-mails (Microsoft Graph, IMAP, fichiers .eml) |
| `immo/extraction.py` | reconnaissance des annonces dans les e-mails |
| `immo/importeur.py` | doublons, enrichissement, orchestration |
| `immo/geo.py` | géolocalisation, frontière, trajets |
| `immo/frais.py` | frais d'acquisition et coût total |
| `immo/score.py` | critères et score |
| `immo/parametres.py` | liste de tous les paramètres modifiables |
| `tests/test_base.py` | tests automatiques : `.venv\Scripts\python -m pytest` |
