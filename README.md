# premier-league-match-predictor

Estimer, à partir des performances historiques des équipes, la probabilité qu'un
match de Premier League se termine par une **victoire à domicile**, un **nul**
ou une **victoire à l'extérieur** — avec des probabilités calibrées, pas
seulement un pronostic binaire.

```
Arsenal vs Liverpool

Home win:     48.2%
Draw:         25.7%
Away win:     26.1%

Predicted result: Arsenal win
```

Quatre approches sont implémentées et comparées **out-of-sample**, du plus
simple au plus sophistiqué : régression logistique multinomiale, rating Elo
maison, modèle de buts à la Poisson (économétrie du football), puis Random
Forest / XGBoost. Le tout est validé avec un **backtest walk-forward par
saison** (jamais de split aléatoire sur des matchs historiques) et mesuré en
**accuracy, log loss et Brier score**.

Au-dessus des modèles : les **buteurs probables** de chaque match, une
**simulation Monte Carlo de la saison** (probabilité de titre, de top 4 et de
relégation pour chaque club, sur 10 000 saisons rejouées), et un site web
(FastAPI + React) avec une page qui explique toute la méthode.

## Pourquoi ce projet

Un modèle qui prédit "Arsenal 51%, nul 25%, Liverpool 24%" est beaucoup plus
informatif — et beaucoup plus difficile à bien faire — qu'un modèle qui dit
juste "Arsenal gagne". Ce repo est construit autour de cette idée : chaque
étape (Elo, Poisson, ML) est jugée sur sa **calibration probabiliste**, pas
seulement sur le taux de bonnes réponses.

## Sommaire

- [Lancement rapide (Windows)](#lancement-rapide-windows)
- [Installation](#installation)
- [Récupérer les données](#récupérer-les-données)
- [Lancer le backtest](#lancer-le-backtest)
- [Prédire un match](#prédire-un-match)
- [Interface web](#interface-web)
- [Crests des clubs](#crests-des-clubs)
- [Méthodologie](#méthodologie)
  - [1. Baseline — régression logistique multinomiale](#1-baseline--régression-logistique-multinomiale)
  - [2. Elo Rating](#2-elo-rating)
  - [3. Modèle de buts Poisson](#3-modèle-de-buts-poisson)
  - [4. Machine Learning (Random Forest, XGBoost)](#4-machine-learning-random-forest-xgboost)
- [Effectifs & buteurs probables](#effectifs--buteurs-probables)
- [Simulation de la saison](#simulation-de-la-saison)
- [Meilleur buteur et meilleur passeur](#meilleur-buteur-et-meilleur-passeur)
- [Statistiques réelles](#statistiques-réelles)
- [Bilan de la saison](#bilan-de-la-saison)
- [Validation temporelle (pas de data leakage)](#validation-temporelle-pas-de-data-leakage)
- [Métriques](#métriques)
- [Performances du modèle](#performances-du-modèle)
- [Structure du projet](#structure-du-projet)
- [Sources de données](#sources-de-données)
- [Roadmap](#roadmap)

## Lancement rapide (Windows)

Après l'[installation](#installation) une première fois,
[`run_app.bat`](run_app.bat) lance tout en un double-clic : installe les
dépendances manquantes, construit l'interface web si besoin, démarre l'API
et ouvre `http://localhost:8000` dans le navigateur.

Pour lui donner une icône ([`app.ico`](app.ico)) et le poser où tu veux
(bureau, barre des tâches, dossier du projet) :

```powershell
$dir = "C:\chemin\vers\premier-league-match-predictor"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$dir\PL Predictor.lnk")
$Shortcut.TargetPath = "$dir\run_app.bat"
$Shortcut.WorkingDirectory = $dir
$Shortcut.IconLocation = "$dir\app.ico"
$Shortcut.Save()
```

Ce raccourci n'est pas versionné (il contiendrait un chemin absolu propre à
ta machine) : chacun le régénère avec la commande ci-dessus.

## Installation

```bash
git clone https://github.com/<votre-user>/premier-league-match-predictor.git
cd premier-league-match-predictor
python -m venv .venv && .venv\Scripts\activate   # ou `source .venv/bin/activate` sous Linux/Mac
pip install -r requirements.txt
pip install -e .
```

L'interface web React (voir [Interface web](#interface-web)) nécessite en
plus [Node.js](https://nodejs.org/) ≥ 18 (`npm install` dans `frontend/`) ;
le dashboard Streamlit legacy n'en a pas besoin.

## Récupérer les données

Les données historiques (scores, saison par saison, depuis 2000) viennent de
[football-data.co.uk](https://www.football-data.co.uk/englandm.php) — des CSV
gratuits, sans clé API, avec un historique long, indispensables pour le
backtest walk-forward et l'entraînement du Elo/Poisson.

```bash
python scripts/download_data.py
# ou une plage de saisons précise :
python scripts/download_data.py --start-year 2010 --end-year 2024
```

Les fichiers sont enregistrés dans `data/raw/` (ignorés par git — voir
`.gitignore` — chacun peut les re-télécharger en une commande).

> Optionnel : pour peupler le sélecteur "prochains matchs" du dashboard avec
> le calendrier réel à venir, on peut aussi s'appuyer sur
> [tarun7r/Premier-League-API](https://github.com/tarun7r/Premier-League-API)
> (`pip install git+https://github.com/tarun7r/Premier-League-API`). Voir
> [`src/pl_predictor/data/fixtures_api.py`](src/pl_predictor/data/fixtures_api.py) —
> cette API n'a pas d'historique complet donc elle n'est **pas** utilisée pour
> l'entraînement, seulement pour l'affichage des fixtures à venir.

Pour les effectifs/stats joueurs (buteurs probables) :

```bash
python scripts/download_player_data.py
```

Voir [Effectifs & buteurs probables](#effectifs--buteurs-probables) pour la
méthodologie complète.

## Lancer le backtest

```bash
python scripts/run_backtest.py
```

Ça entraîne chaque modèle en walk-forward (voir plus bas) et écrit :

- `reports/backtest_per_season.csv` — métriques saison par saison, par modèle
- `reports/backtest_summary.csv` — moyenne pondérée par nombre de matchs, tous modèles confondus

## Prédire un match

```bash
python scripts/predict_match.py "Arsenal" "Liverpool"
```

```
Arsenal vs Liverpool

Home win:      48.2%
Draw:          25.7%
Away win:      26.1%

Predicted result: Arsenal win

Expected goals
Arsenal        1.72
Liverpool      1.18

Most likely scores
1-1             11.4%
1-0              9.8%
2-1              8.7%
2-0              7.5%
0-0              6.9%
```

## Interface web

### React (recommandé)

Backend FastAPI (fine couche HTTP sur `pl_predictor`, sans dupliquer la
logique) + frontend React/Vite en cinq pages :

- **Match** : l'affiche sert de titre, et chaque nom de club se clique pour
  changer d'équipe. Probabilités victoire/nul/défaite, buts attendus, grille
  des scores exacts (carte de chaleur), buteurs probables. La prédiction se
  met à jour dès qu'on change d'équipe.
- **Stats** : les chiffres réels, sans modèle. Classement avec la forme sur
  les 5 derniers matchs, meilleurs buteurs et passeurs, derniers résultats.
- **Projections** : course au titre, lutte pour le maintien, meilleur buteur
  et meilleur passeur en fin de saison, et classement projeté avec pour chaque
  club la distribution complète de ses positions finales.
- **Bilan** : nos prédictions de la saison face aux vrais résultats, journée
  par journée (bon résultat, score exact, buteur favori), comparées à ce que
  nos propres probabilités annonçaient.
- **Méthode** : toute la méthode expliquée, formules comprises (KaTeX), avec
  le tableau du backtest et les limites du modèle.

Parti pris graphique : une interface monochrome (graphite, filets fins, une
seule famille de caractères, Archivo, condensée pour les titres et les
chiffres), pour que les données soient les seules à porter de la couleur. Les
graphiques ne reprennent pas les couleurs des clubs (Arsenal et Liverpool,
par exemple, ont deux rouges quasi identiques) : domicile = bleu, nul = gris,
extérieur = orange, une palette validée pour la lisibilité par les
daltoniens. L'identité des clubs passe par les crests.

**Développement** (deux process, avec rechargement à chaud) :

```bash
# terminal 1
uvicorn api.main:app --reload --port 8000
# terminal 2
cd frontend && npm install && npm run dev
```

Puis ouvrir l'URL donnée par Vite (typiquement `http://localhost:5173`).

**Usage local ("prod")**, un seul process :

```bash
cd frontend && npm install && npm run build && cd ..
uvicorn api.main:app --port 8000
```

Puis ouvrir `http://localhost:8000` — FastAPI sert directement le front
buildé en plus de l'API.

Pour les vrais crests des clubs (best-effort, voir
[Crests des clubs](#crests-des-clubs)) :

```bash
python scripts/download_club_crests.py
```

### Streamlit (legacy)

Gardé comme interface de secours, plus rapide à lancer, sans étape de build :

```bash
streamlit run dashboard/app.py
```

Sélectionne une équipe à domicile et une équipe à l'extérieur, et obtiens les
probabilités H/D/A, les buts attendus (xG), les scores les plus probables et
les buteurs probables — plus un onglet avec les performances historiques du
backtest.

## Crests des clubs

Les logos sont inclus dans `frontend/public/crests/`, récupérés sur Wikipedia
par [`scripts/download_club_crests.py`](scripts/download_club_crests.py). Il
suffit de relancer ce script quand un club promu arrive : il ne télécharge
que les logos manquants. L'API `pageimages` de Wikipedia exclut les logos
("non-free content"), donc le script analyse la liste des images de la page
de chaque club et choisit le meilleur candidat par heuristique sur le nom de
fichier. Un club sans logo affiche un monogramme coloré — voir
[`ClubCrest.tsx`](frontend/src/components/ClubCrest.tsx) — jamais d'icône
cassée.

> Les logos sont des marques déposées appartenant à leurs clubs respectifs.
> Ils sont utilisés ici uniquement pour identifier les équipes, dans un projet
> personnel et non commercial sans lien avec la Premier League ni les clubs.

## Méthodologie

### 1. Baseline — régression logistique multinomiale

Variables explicatives simples calculées **sans fuite temporelle** (voir
[Validation temporelle](#validation-temporelle-pas-de-data-leakage)) :
forme sur les 5 derniers matchs (points, buts marqués/encaissés), forme
spécifique domicile/extérieur, position et points par match dans le classement
en cours de saison, écart Elo.

$$P(Y_i = k \mid X_i), \quad Y_i \in \{\text{Home win}, \text{Draw}, \text{Away win}\}$$

Implémentation : [`src/pl_predictor/models/baseline_logreg.py`](src/pl_predictor/models/baseline_logreg.py).

### 2. Elo Rating

Un système Elo maison ([`src/pl_predictor/features/elo.py`](src/pl_predictor/features/elo.py)),
avec bonus d'avantage du terrain et multiplicateur de marge de victoire (une
victoire 4-0 déplace plus le rating qu'une victoire 1-0) :

$$Elo_{new} = Elo_{old} + K \cdot (S - E)$$

où `E` est le score attendu (formule logistique standard, ajustée de
l'avantage du terrain) et `S` le résultat réel (1 victoire, 0.5 nul, 0
défaite). L'écart de rating Elo est ensuite utilisé comme variable explicative
(seule, dans une régression logistique — "modèle Elo" du backtest) et comme
feature dans le modèle baseline.

```
Manchester City    1874
Arsenal             1841
Liverpool           1819
Chelsea             1762
...
```

(classement complet obtenu via `EloRatings.as_table()`)

### 3. Modèle de buts Poisson

Les buts à domicile et à l'extérieur sont modélisés séparément :

$$Goals_{home} \sim \text{Poisson}(\lambda_{home}), \qquad Goals_{away} \sim \text{Poisson}(\lambda_{away})$$

$$\log(\lambda_{home}) = \alpha + Attack_{home} - Defense_{away} + HomeAdvantage$$
$$\log(\lambda_{away}) = \alpha + Attack_{away} - Defense_{home}$$

En pratique, ce modèle est estimé comme une régression de Poisson avec effets
fixes par équipe (attaque + défense), sur les données mises en "long format"
(une ligne par équipe et par match) — voir
[`src/pl_predictor/models/poisson_model.py`](src/pl_predictor/models/poisson_model.py).
Trois détails comptent beaucoup :

- **Pondération temporelle** (Dixon & Coles, 1997) : un match compte deux
  fois moins tous les 365 jours, $w = 0.5^{\text{âge}/365}$. Sans ça, un club
  promu est jugé sur sa dernière saison en Premier League, parfois vieille de
  25 ans.
- **Effets d'équipe centrés sur la moyenne de la ligue** : la version manuel
  scolaire retire une équipe de référence, mais alors la pénalité L2 tire
  toutes les équipes mal connues vers *cette* équipe, alphabétiquement la
  première, c'est-à-dire Arsenal. Un promu se retrouvait noté presque comme
  Arsenal. Avec toutes les équipes encodées et un intercept, le rétrécissement
  se fait vers la moyenne.
- **Régularisation choisie pour l'usage réel** : le site réentraîne le modèle
  en cours de saison, où un promu n'a que quelques matchs récents. Évaluée
  avec un réentraînement chaque semaine
  ([`run_in_season_rolling`](src/pl_predictor/evaluation/backtest.py)), une
  pénalité trop faible laissait 5 matchs dicter la note d'une équipe : une
  première version projetait un promu à 21 points. Log loss sur les matchs de
  début de saison : 0,999 avec α = 0,001, contre **0,980 avec α = 0,01**.

Ces réglages sont choisis par
[`scripts/tune_poisson.py`](scripts/tune_poisson.py) sur les saisons
2008-09 → 2012-13 uniquement, toutes antérieures aux saisons du backtest
publié, pour ne pas "tricher" en réglant le modèle sur ses propres données
de test. Un effet "promu" a aussi été testé, sans gain mesurable : il reste
disponible mais désactivé.

On en tire la matrice complète des scores probables :

```
        Liverpool
        0     1     2     3
Arsenal
0      8.1%  7.4%  3.4%  1.0%
1      9.6%  8.8%  4.0%  1.2%
2      5.7%  5.2%  2.4%  0.7%
3      2.2%  2.0%  0.9%  0.3%
```

puis les probabilités d'issue par sommation :

$$P(\text{Home win}) = \sum_{i>j} P(\text{Home}=i, \text{Away}=j)$$

(et de même pour le nul et la victoire à l'extérieur).

### 4. Machine Learning (Random Forest, XGBoost)

Sur les mêmes features engineerées, pour voir si des modèles plus flexibles
apportent réellement quelque chose **out-of-sample**, ou s'ils se contentent
de sur-apprendre le bruit historique — voir
[`src/pl_predictor/models/ml_models.py`](src/pl_predictor/models/ml_models.py).

## Effectifs & buteurs probables

Les modèles ci-dessus raisonnent au niveau équipe. Mais un attaquant en forme
peut faire pencher un match indépendamment du niveau global de son équipe —
d'où une couche supplémentaire, au niveau joueur.

**Restriction aux 20 équipes actuelles.** Le picker d'équipes (dashboard et
CLI) ne propose que les clubs réellement en Premier League cette saison, pas
les ~50 clubs passés par la division sur les 25 ans d'historique. Ces 20
équipes sont dérivées directement de la saison la plus récente présente dans
`data/raw/` — voir
[`get_current_season_teams`](src/pl_predictor/data/load.py).

**Effectifs & stats joueurs.** Récupérés depuis FBref via la librairie
[`soccerdata`](https://github.com/probberechts/soccerdata) (qui gère déjà le
parsing des tableaux FBref, planqués dans des commentaires HTML, ainsi que le
cache local et le rate-limiting — pas de scraper maison) :

```bash
python scripts/download_player_data.py
```

Chaque appel écrit un snapshot horodaté dans `data/players/snapshots/` et met
à jour `data/players/latest.csv` — voir
[`src/pl_predictor/data/player_stats.py`](src/pl_predictor/data/player_stats.py).
Contrairement à `data/raw/` (résultats bruts) et aux crests (marques
déposées, voir plus bas), `data/players/` **est versionné** : ce ne sont que
des faits publics (effectif, buts, minutes), et les garder dans le dépôt
permet à la routine cloud hebdomadaire de calculer la "forme récente" d'une
semaine à l'autre, et à n'importe quel checkout local de récupérer un
effectif à jour avec un simple `git pull`, sans avoir à re-scraper FBref.

> Les données reflètent toujours FBref au moment du scrape — pas de valeur
> modifiée à la main. Un transfert de joueur n'apparaît qu'une fois que FBref
> l'a répercuté ; la routine cloud du mercredi relance justement
> `download_player_data.py` chaque semaine pour rester à jour, et signale
> explicitement dans son rapport tout changement de club détecté d'un
> snapshot à l'autre.

**Modèle de buteurs probables**
([`src/pl_predictor/models/player_goals.py`](src/pl_predictor/models/player_goals.py)) :
plutôt que d'ajuster un GLM Poisson par joueur (la plupart marquent trop peu
de buts sur une saison pour qu'une estimation individuelle soit autre chose
que du bruit), le nombre de buts attendus de l'équipe — déjà validé par le
backtest — est **réparti entre les joueurs de l'effectif** :

1. `attack_share` : part de chaque joueur dans les buts de son équipe cette
   saison, **rétrécie vers un a priori** avec $K = 8$ buts fictifs :
   $\text{part}_i = (\text{buts}_i + K \cdot \text{a priori}_i) / (\text{buts}_{\text{équipe}} + K)$.
   L'a priori, c'est le temps de jeu × le taux de buts par 90 minutes du
   joueur **la saison précédente** (`data/players/previous_season.csv`), lui
   même rétréci vers le taux moyen de son poste ; un nouveau venu en Premier
   League repart de la moyenne de son poste. Sans rétrécissement, un
   attaquant auteur de 4 des 7 premiers buts de son équipe recevait 57 % de
   tous ses buts futurs ; sans l'historique, après cinq journées, un buteur
   confirmé et un joueur quelconque au même poste étaient indiscernables.
   $K$ est un choix raisonné, pas réglé sur données. `assist_share` applique
   le même traitement aux passes décisives.
2. `recent_form_multiplier` : ratio entre le taux de buts/90 min "récent"
   (delta entre les deux derniers snapshots) et le taux saison, **clippé à
   [0.5, 1.8]** pour ne pas laisser un petit échantillon (une semaine entre
   deux snapshots) s'emballer.
3. Les parts `attack_share × recent_form_multiplier` sont renormalisées pour
   sommer à 1 sur l'effectif, puis multipliées par le nombre de buts attendus
   de l'équipe — la somme des buts attendus par joueur retombe donc
   exactement sur le total d'équipe déjà backtesté.
4. `P(joueur marque ≥ 1 but) = 1 - exp(-λ_joueur)` (loi de Poisson).

**Limite assumée sur la "forme récente"** : au tout premier lancement, un
seul snapshot existe, donc le multiplicateur de forme reste neutre (1.0) et
le modèle se rabat sur le taux saison — c'est un choix honnête plutôt que de
fabriquer un signal de récence à partir d'une seule mesure. Le signal
s'affine ensuite au fil des rafraîchissements successifs de
`data/players/`. Deux snapshots de saisons différentes ne sont jamais
comparés : les totaux repartent de zéro chaque mois d'août.

**Transferts en cours de saison** : FBref liste un joueur transféré une fois
par club. Il est identifié par nom + année de naissance + nationalité (pour
ne pas fusionner deux homonymes), et son club actuel est celui où ses minutes
ont augmenté depuis le relevé précédent, ou à défaut celui où il a le plus
joué. Il n'apparaît plus parmi les buteurs probables de son ancien club.

## Simulation de la saison

```bash
python scripts/simulate_season.py
```

```
2026-27: 50 matches played, 330 remaining - 10,000 simulations in 0.25s

Team              Pts   xPts   Title   Top 4  Releg.
Man City           15   79.9   62.3%   99.0%    0.0%
Arsenal            12   76.0   32.7%   96.8%    0.0%
Liverpool           9   64.8    3.4%   63.9%    0.0%
...
```

[`src/pl_predictor/simulation.py`](src/pl_predictor/simulation.py) :

1. Le classement réel est calculé à partir des matchs déjà joués.
2. Les matchs restants se déduisent **sans calendrier externe** : une saison
   est un double round-robin, donc restant = tous les couples (domicile,
   extérieur) − ceux déjà joués.
3. Chaque match restant reçoit ses deux λ du modèle Poisson, et on tire
   10 000 scores par match.
4. Chaque saison simulée est classée (points, différence de buts, buts
   marqués, puis tirage au sort).
5. Probabilité d'un événement = part des saisons où il se produit.

Entièrement vectorisé : des matrices d'incidence (matchs × équipes)
transforment les scores simulés en totaux par équipe en deux produits
matriciels. 3,3 millions de matchs tirés en un quart de seconde.

**Limite** : la force des équipes est figée pour toute la simulation
(blessures, transferts et forme ne sont pas modélisés, et l'incertitude sur la
force elle-même n'est pas propagée), donc les probabilités du favori sont un
peu trop tranchées, surtout en début de saison.

## Meilleur buteur et meilleur passeur

```
Top scorer              Team              Now   Proj.   P(top)
Erling Haaland          Man City            5    28.0    62.1%
Alexander Isak          Liverpool           4    25.3    31.9%
Bukayo Saka             Arsenal             3    18.0     1.7%
...
Top assists             Team              Now   Proj.   P(top)
Cody Gakpo              Liverpool           3    15.2    36.1%
Evanilson               Bournemouth         3    13.2    14.6%
...
```

[`src/pl_predictor/season_awards.py`](src/pl_predictor/season_awards.py)
pousse la simulation au niveau des joueurs :

1. Les buts qu'un club doit encore marquer suivent une loi de Poisson de
   moyenne $\Lambda_{\text{club}}$, la somme de ses buts attendus sur ses matchs
   restants.
2. Chaque but revient au joueur $i$ avec une probabilité
   $\rho \cdot \text{part}_i$ : $\text{part}_i$ est la part décrite plus haut, et
   $\rho$ la proportion de buts attribués à un buteur (le reste, ce sont des
   CSC), **mesurée sur la saison en cours** (0,95). Pour les passes, $\rho$
   devient le nombre de passes décisives par but (0,69).
3. **Amincissement de Poisson** : répartir au hasard un nombre poissonnien
   donne pour chaque joueur un nombre lui aussi poissonnien,
   $\text{Poisson}(\Lambda_{\text{club}} \cdot \rho \cdot \text{part}_i)$, et
   indépendant des autres. On tire donc directement le total futur de chaque
   joueur, 10 000 fois, sans simuler but par but. C'est exact sous les
   hypothèses du modèle, et ça tourne en 0,6 s.
4. Total final = buts déjà marqués (dans tous ses clubs, comme pour le
   Soulier d'or) + buts simulés (dans son club actuel seulement). En cas
   d'égalité dans une saison simulée, le titre est partagé.

La page Projections affiche pour chaque joueur la projection de fin de saison
et l'intervalle où tombent 8 saisons simulées sur 10.

## Statistiques réelles

[`src/pl_predictor/stats.py`](src/pl_predictor/stats.py) alimente la page
Stats sans aucun modèle : classement calculé à partir des matchs joués, forme
sur les 5 derniers matchs, derniers résultats, meilleurs buteurs et passeurs
(un joueur transféré cumule ses deux clubs). Quand la liste des 10 premiers
coupe un groupe d'ex æquo, la page le signale ("Et 1 autre joueur à 3 buts")
plutôt que d'en choisir certains arbitrairement.

## Bilan de la saison

```bash
python scripts/download_match_players.py   # feuilles de match FBref (buteurs, minutes), en incrémental
python scripts/build_track_record.py
```

```
2026-27: 50 matches over 5 matchweeks (2.9s)

Result (H/D/A)   23/50  =  46%   expected 26.6 (80% range 22-31)
Exact score       5/50  =  10%   expected 5.8 (80% range 3-9)
Top scorer pick   ...
Log loss        1.042   (reference, historical frequencies: 1.119)
```

[`src/pl_predictor/track_record.py`](src/pl_predictor/track_record.py)
reconstruit le prédicteur **avant chaque journée** avec les seules données
disponibles à ce moment-là, puis le confronte aux résultats :

- Les modèles (Elo, logistique, Poisson) sont réentraînés sur les matchs
  antérieurs au premier match de la journée.
- Les parts des joueurs sont recalculées à partir des **feuilles de match**
  antérieures ([`match_players.py`](src/pl_predictor/data/match_players.py)),
  jamais à partir des totaux de saison actuels, qui contiennent déjà les buts
  qu'on cherche à prédire. Un test vérifie que modifier les résultats d'une
  journée ne change aucune prédiction de cette journée.
- Chaque indicateur est comparé à ce que nos probabilités annonçaient : le
  nombre de réussites a pour moyenne $\sum p$ et pour variance
  $\sum p(1-p)$, d'où une fourchette à 80 %. Avec 50 matchs, un écart de
  quelques points relève du hasard ; c'est la sortie durable de la fourchette
  qui signalerait un problème de calibration.

FBref limite fortement le rythme des requêtes (~1 min par feuille de match
ici) : les feuilles sont donc stockées dans `data/players/match_stats_<saison>.csv`
et seuls les nouveaux matchs sont téléchargés (une dizaine par semaine). Le
bilan est recalculé avec le modèle actuel : il mesure le modèle d'aujourd'hui,
pas un historique de ce que le site affichait.

## Validation temporelle (pas de data leakage)

Deux précautions structurent tout le projet :

1. **Les features elles-mêmes sont calculées en un seul passage chronologique** :
   la forme, le classement en cours de saison et le rating Elo d'un match ne
   dépendent que des matchs strictement antérieurs à celui-ci (voir
   [`src/pl_predictor/features/`](src/pl_predictor/features/)). Résultat :
   quel que soit l'endroit où l'on coupe ensuite les données par date, aucune
   fuite du futur ne peut se glisser dans les colonnes.

2. **Le split train/test est un walk-forward saison par saison**, jamais un
   `train_test_split(random=True)` :

```
2010-2018 → training       2010-2019 → training       2010-2020 → training
2019       → test          2020       → test          2021       → test
```

Implémenté dans [`src/pl_predictor/evaluation/backtest.py`](src/pl_predictor/evaluation/backtest.py)
et piloté par `scripts/run_backtest.py`.

## Métriques

- **Accuracy** — `# prédictions correctes / # matchs`. Facile à lire, mais
  aveugle à la confiance : "Arsenal 34%" et "Arsenal 90%" comptent pareil si
  Arsenal gagne.
- **Log loss** — $-\frac{1}{N}\sum_i \log P(y_i)$. Punit sévèrement une
  prédiction confiante et fausse.
- **Brier score** — erreur quadratique moyenne entre les probabilités
  prédites et le résultat one-hot. Plus intuitif que le log loss, même
  sensibilité à la calibration.

Une baseline naïve ("toujours prédire la fréquence historique H/D/A") est
incluse dans chaque backtest (`naive_base_rate`) : un modèle qui ne la bat pas
sur log loss/Brier n'apporte rien.

## Performances du modèle

Backtest walk-forward sur 14 saisons de test (2013-14 → début de 2026-27,
soit 4 990 matchs), en s'entraînant à chaque fois uniquement sur les saisons
antérieures. Généré par `python scripts/run_backtest.py` ; voir
[`reports/backtest_summary.csv`](reports/backtest_summary.csv) et
[`reports/backtest_per_season.csv`](reports/backtest_per_season.csv) pour le
détail saison par saison.

| model              | accuracy | log_loss | brier_score |
|--------------------|---------:|---------:|-------------:|
| elo_logistic       |   53.7%  |  0.9783  |  0.5801     |
| baseline_logistic  |   53.9%  |  0.9786  |  0.5801     |
| random_forest      |   53.7%  |  0.9813  |  0.5831     |
| xgboost            |   53.4%  |  0.9853  |  0.5845     |
| poisson            |   52.5%  |  0.9876  |  0.5878     |
| naive_base_rate    |   44.5%  |  1.0686  |  0.6463     |

Le modèle Poisson a beaucoup progressé avec la pondération temporelle et le
centrage des effets d'équipe (log loss **1,009 → 0,988**, voir
[Modèle de buts Poisson](#3-modèle-de-buts-poisson)). Il reste un cran
derrière l'Elo dans *ce* backtest, qui entraîne avant chaque saison ; sa
régularisation est volontairement réglée pour le cas d'usage réel du site,
un réentraînement en cours de saison.

Quelques enseignements :

- **Tout modèle bat largement la baseline naïve** (fréquence historique
  H/D/A) sur les trois métriques — le signal Elo/forme/classement apporte
  bien de l'information out-of-sample.
- **La régression logistique (baseline ou Elo seul) et le Random Forest sont
  quasiment à égalité**, et devancent légèrement XGBoost : sur ce problème,
  la complexité supplémentaire des arbres n'apporte pas grand-chose une fois
  qu'on valide correctement dans le temps — un résultat cohérent avec la
  littérature sur la prédiction de matchs de football.
- **Le modèle Poisson est le seul à produire une distribution de scores
  complète** (buts attendus, grille des scores, buteurs, simulation de
  saison) : c'est pour ces usages qu'il est gardé, pas pour l'issue
  victoire/nul/défaite, où l'Elo reste un peu meilleur.
- Les deux modèles (Elo/logistique pour V/N/D, Poisson pour les scores) sont
  ajustés indépendamment et peuvent occasionnellement se contredire sur un
  match donné : c'est attendu, chacun capture l'avantage du terrain et la
  force des équipes à sa façon.

## Structure du projet

```
premier-league-match-predictor/
├── run_app.bat                  # lance tout en un double-clic (Windows)
├── app.ico                       # icône du raccourci créé par run_app.bat
├── data/
│   ├── raw/                  # CSV football-data.co.uk téléchargés (non versionnés)
│   ├── processed/            # tables de features mises en cache (non versionnées)
│   └── players/               # snapshots FBref effectifs/stats joueurs (versionnés)
├── src/pl_predictor/
│   ├── config.py              # chemins, constantes, codes de saison
│   ├── data/
│   │   ├── download.py         # téléchargement football-data.co.uk
│   │   ├── load.py              # nettoyage + concaténation en une table de matchs
│   │   ├── player_stats.py       # effectifs/stats joueurs via FBref (soccerdata)
│   │   ├── match_players.py       # calendrier + feuilles de match FBref (buteurs, minutes)
│   │   └── fixtures_api.py        # wrapper optionnel Premier-League-API (fixtures à venir)
│   ├── features/
│   │   ├── elo.py               # système de rating Elo maison
│   │   └── engineering.py        # forme, classement en cours de saison
│   ├── models/
│   │   ├── base.py               # interface commune OutcomeModel
│   │   ├── naive.py               # baseline fréquence historique
│   │   ├── baseline_logreg.py      # régression logistique multinomiale (+ modèle "Elo")
│   │   ├── poisson_model.py         # modèle de buts Poisson (attaque/défense)
│   │   ├── ml_models.py              # Random Forest, XGBoost
│   │   └── player_goals.py            # buteurs probables (répartition joueur du λ équipe)
│   ├── evaluation/
│   │   ├── metrics.py             # accuracy, log loss, Brier score
│   │   └── backtest.py             # walk-forward par saison + évaluation glissante en cours de saison
│   ├── simulation.py              # Monte Carlo de la fin de saison (titre, top 4, relégation)
│   ├── season_awards.py           # Monte Carlo meilleur buteur / meilleur passeur
│   ├── stats.py                   # statistiques réelles (classement, forme, leaders)
│   ├── track_record.py            # bilan : prédictions reconstituées vs résultats
│   └── predict.py                 # API haut niveau utilisée par le dashboard/CLI/l'API
├── api/main.py                  # backend FastAPI (fine couche HTTP sur pl_predictor)
├── frontend/                    # front React/Vite
│   ├── src/
│   │   ├── pages/                 # MatchPage, StatsPage, SeasonPage, RecordPage, HowItWorksPage
│   │   ├── components/            # TeamPicker, OutcomeBar, ScoreHeatmap, AwardTable, LeaderList, FormGuide, ...
│   │   ├── data/clubColors.ts      # couleurs (monogrammes de repli) + slugs des clubs
│   │   └── api.ts                   # wrapper fetch typé vers l'API FastAPI
│   └── public/crests/              # logos des clubs (Wikipedia, voir plus haut)
├── dashboard/app.py            # dashboard Streamlit (legacy, gardé en secours)
├── scripts/
│   ├── download_data.py
│   ├── download_player_data.py
│   ├── download_club_crests.py
│   ├── run_backtest.py
│   ├── tune_poisson.py             # réglage du Poisson sur saisons de validation
│   ├── simulate_season.py          # titre / relégation + meilleur buteur / passeur
│   ├── download_match_players.py   # feuilles de match FBref, en incrémental
│   ├── build_track_record.py       # bilan de la saison -> reports/track_record.json
│   ├── wait_for_server.py          # utilisé par run_app.bat
│   └── predict_match.py
├── tests/                       # tests unitaires (Elo, Poisson, métriques, buteurs, simulation, trophées, stats)
└── reports/                      # résultats de backtest générés
```

## Sources de données

- [football-data.co.uk](https://www.football-data.co.uk/englandm.php) — historique
  des résultats de Premier League (utilisé pour l'entraînement et le backtest).
- [FBref](https://fbref.com/) (via [`soccerdata`](https://github.com/probberechts/soccerdata)) —
  effectifs et stats joueurs de la saison en cours (buts, minutes), utilisés
  pour le modèle de buteurs probables. Scraping fait à un rythme raisonnable
  (la librairie gère déjà le cache et le rate-limiting) ; évite de relancer
  `download_player_data.py` en boucle.
- [tarun7r/Premier-League-API](https://github.com/tarun7r/Premier-League-API) — client
  non officiel pour les fixtures/classements en cours (utilisé uniquement pour
  le calendrier à venir dans le dashboard, en option).

## Roadmap

**Fait** : Elo/Poisson/ML avec backtest walk-forward (Phase 0), restriction
aux 20 équipes actuelles + buteurs probables (Phase 1), API FastAPI + front
React avec vrais crests des clubs (Phase 2), simulation de saison, Poisson
pondéré dans le temps et refonte du site (Phase 3), meilleur buteur/passeur,
page de statistiques réelles et gestion des transferts (Phase 4), bilan de la
saison sans fuite d'information (Phase 5).

**Prochain chantier possible** :

- **Enrichissement des données joueurs** : intégrer Understat (xG par
  joueur/tir) pour affiner le modèle de buteurs au-delà du simple partage de
  `attack_share × recent_form_multiplier`.
- **Calendrier réel** : brancher `/api/fixtures`
  ([`fixtures_api.py`](src/pl_predictor/data/fixtures_api.py), déjà prêt côté
  backend) sur le front pour proposer directement les prochains matchs plutôt
  que de choisir les deux équipes à la main.
- **Incertitude sur la force des équipes** dans la simulation (par exemple
  tirer les paramètres de chaque saison simulée autour de leur estimation),
  pour des probabilités de titre moins tranchées en début de saison.
- **Déploiement** : usage local uniquement pour l'instant (pas de Docker/
  hébergement prévu).

## Licence

MIT — voir [LICENSE](LICENSE).
