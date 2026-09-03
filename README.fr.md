# Sismo-LA — nœud sismique de quartier, auto-calibré sur l’USGS

[English](README.md) · [Français](README.fr.md)

Le comté de Los Angeles (~10 millions d’habitants) est sur des failles très
actives et déjà densément instrumenté. Le catalogue USGS publie magnitude, lieu
et profondeur en quelques minutes. Ce dépôt est un nœud dans ce cadre, sur
Arduino UNO Q, à environ 80 $.

Question testée :

> Un nœud à ce prix peut-il détecter un séisme et estimer sa magnitude, sans
> surveillance et sans calibration manuelle ?

Page publique (sans coordonnées) : <https://medialoco.github.io/sismo-la/>

![Tableau de bord opérateur : cercles USGS et estimations de l’appareil](docs/images/dashboard-replay.png)

*Tableau de bord opérateur. Événements USGS en cercles colorés ; estimations de
l’appareil en rouge ; trois modèles à droite. Capture en `--replay` : amplitudes
synthétiques, 38× trop grandes, qui mesurent le logiciel
([résidus replay](#replay-et-résidus-hors-échantillon)).*

## État (2 septembre 2026)

La station tourne sur sa propre alimentation et le WiFi, sans ordinateur
branché. Elle détecte des secousses, les recoupe avec l’USGS, journalise, et
publie un instantané JSON toutes les 20 minutes (un heartbeat est forcé après
4 h si le fichier est inchangé). Après un vrai débranchement, le tableau de
bord a répondu en **4 min 24 s**. Une panne de 5 h 43 min a montré le MCU
redémarrant dans sa propre flash.

Le 2 septembre 2026 elle a enregistré un séisme catalogué dans son enveloppe
continue : **`ci41540608`**, M3,2, Ontario, CA, 12:37:12 UTC. Enveloppe z = 4,34
(seuil 4,0), crête 0,001095 g, baseline 0,0003816 g, fenêtre 20 s, décalage 24 s.

Le déclencheur STA/LTA aveugle n’a pas tiré (amplitude requise ~0,0033 g). La
calibration d’amplitude est à **0 sur 8**. Les confirmations sont exclues de cet
ajustement (`retro.feed_calibration: false`).

## Détection et confirmation

| Canal | Définition | Alimente la calibration d’amplitude |
|---|---|---|
| Détection | le STA/LTA a tiré sans l’heure catalogue | oui, une fois l’USGS apparié |
| Confirmation | l’origine catalogue a choisi la fenêtre ; l’enveloppe y était élevée | non |

Le journal, le tableau de bord et la page publique tiennent les deux listes
séparées.

## Méthode

1. L’IMU réduit chaque déclenchement à PGA, durée et fréquence dominante.
2. Le côté Linux interroge le FDSN USGS (contexte carte ≥ M0,5, appariements de
   calibration ≥ M2, rayon 160 km).
3. Une coincidence temporelle est un couple étiqueté (mesure, catalogue). Un
   déclenchement sans correspondance est un exemple de bruit.
4. Trois modèles se réajustent en ligne. Après convergence ils tournent hors
   ligne, depuis le disque.

| Modèle | Entrée → sortie | Utilisable après |
|---|---|---|
| Calibration d’amplitude | log10(PGA), log10(distance) → magnitude | 8 correspondances |
| Modèle de distance | durée, fréquence dominante → distance épicentrale | 5 correspondances |
| Filtre de bruit | PGA, durée, fréquence → P(séisme) | 3 de chaque classe |

Modèle d’amplitude : `M ≈ a·log10(PGA) + b·log10(R) + c`. Les coefficients
absorbent ce capteur, ce montage, ce bâtiment et ce sol. Voir
[`docs/calibration.md`](docs/calibration.md).

Une enveloppe continue (crête et RMS, 0,7–12 Hz, 1 échantillon / s) est cherchée
à l’instant d’arrivée impliqué par chaque origine catalogue. Cette recherche
porte sur une poignée de fenêtres par événement, contre ~170 000 fenêtres
STA/LTA aveugles par jour : elle peut se placer plus près du bruit et moyenner
le train d’ondes. Sur le bruit de cette station, le gain est un **facteur 7–8
en amplitude (une unité de magnitude)**.

## Loi de mouvement du sol

La forme utilisée ici a été contrôlée sur **12 324 valeurs de PGA ShakeMap**
issues de 40 séismes du sud de la Californie (M3,03–5,51, 3–200 km,
1 006 stations). Les coefficients précédents surestimaient l’amplitude de
37,9×. Le réajustement est

`0,867·M − 1,740·log10 R − 3,305`

dispersion 0,390 log10, R² = 0,80. Les énoncés faits avec l’ancienne loi étaient
hauts d’environ deux unités de magnitude.

## Seuil de détection

Le micrologiciel a un rapport STA/LTA, pas un seuil en g fixe. Le plancher est
une propriété du site. Sur 163 déclenchements, la plus petite crête qui a tiré
est **0,0034 g** (0,0044 g dans la fenêtre la plus calme). Via la loi
réajustée, cela devient une magnitude requise, ±0,45 (1σ) ; sous M3 les valeurs
sont des extrapolations :

| | 10 km | 30 km | 50 km | 100 km | 160 km |
|---|---|---|---|---|---|
| Déclencheur aveugle | 3,1 | 3,9 | 4,3 | 4,9 | 5,3 |
| Recherche rétrospective | 2,1 | 2,9 | 3,3 | 3,9 | 4,3 |

Convolution avec 2 185 événements catalogue (M ≥ 2, 160 km, 5 ans) et la
dispersion 0,39 log10, amplification de site ×1 à ×4 :

| | événements / an | attente moyenne | P(≥1 avant le 13 sep 2026) |
|---|---|---|---|
| Déclencheur aveugle | 2,0 – 9,8 | 37–184 jours | 6–28 % |
| Déclencheur + recherche rétrospective | 9,9 – 36,9 | 10–37 jours | 28–70 % |

La ligne rétrospective suppose le site au repos (~50 % des heures ici). À une
heure passante, l’enveloppe erre d’environ ×4 ; à une heure calme, ~3 %.
L’enregistrement d’enveloppe commence le 1er septembre 2026 ; les heures
antérieures ne sont pas cherchables.

## Confirmation `ci41540608`

| | |
|---|---|
| Origine | 2026-09-02 12:37:12 UTC, M3,2, Ontario, CA |
| Enveloppe | z = 4,34 (seuil 4,0), crête 0,001095 g, baseline 0,0003816 g |
| Fenêtre | 20 s, décalage 24 s après l’origine (temps de trajet S ordinaire) |
| STA/LTA aveugle | ~0,0033 g requis ; pas de déclenchement |
| Site | au repos (bruit électrique du capteur) |
| Calibration | inchangée (0 sur 8), par construction |

Un événement. z = 4,34 est une marge modeste. Le taux de fausse confirmation
1 sur 1 200 a été calculé sur du bruit de capteur pur ; ce site produit aussi
des impulsions locales, donc ce taux est une borne supérieure tant qu’il n’est
pas recalculé sur l’enveloppe enregistrée. Le test de significativité n’utilise
pas le décalage ; les 24 s sont indépendants du seuil z.

## Autres mesures

| Observation | Valeur |
|---|---|
| Taux de déclenchement après remonte (bureau → meilleur couplage) | 22,6 → 3,2 / h (−86 %) ; plancher 0,00087 → 0,00066 g (−24 %) |
| Mise sous tension → tableau de bord | 4 min 24 s (sidecar watchdog ; App Lab arrête sinon le conteneur au boot) |
| Fréquence dominante (après correction signe centré / non centré) | taps à 2,6 / 5,0 / 10,6 Hz ; le bug rapportait ~25 Hz sur tout signal |

La vivacité est le battement MCU (~10 s). Un HTTP 200 du tableau de bord ne
prouve pas que le capteur tourne. `health.stale` pilote le badge public et une
bannière `STATION DEGRADED`.

## Audit catalogue

Pour chaque événement catalogué, la station calcule l’amplitude attendue via la
loi réajustée et lit le bruit enregistré à cet instant. Classes : **hors de
portée**, **marginal**, **déclenché**, **confirmé**, **aurait dû être vu**.
Seule la dernière est une panne.

30 jours au 2 septembre 2026 : **19 événements catalogués, 1 confirmé, 0 aurait-
dû-être-vu**. L’audit publié est ces trois comptes. Quels événements étaient à
portée encode une distance et n’est pas publié. Méthode :
[`docs/expected-vs-observed.md`](docs/expected-vs-observed.md).

## Replay et résidus hors échantillon

`--replay` synthétise les amplitudes à partir de M et R catalogue via la loi
*d’avant le réajustement*, donc 38× trop grandes (conservé pour que la démo
passe le déclencheur). Le calibreur ajuste alors l’inverse de cette loi. Les
résidus testent le pipeline.

Le RMSE du tableau de bord est un résidu intra-échantillon avec la *vraie*
distance catalogue. En direct, la distance est *estimée*. `python audit.py`
note le journal de façon préquentielle :

| Estimateur | run A (11 pts) | run B (27 pts) |
|---|---|---|
| Intra-échantillon, vraie distance (panneau) | 0,20 Mw | 0,18 Mw |
| Hors échantillon, vraie distance | 0,30 Mw | 0,21 Mw |
| Hors échantillon, distance estimée (chemin opérationnel) | 1,10 Mw | 0,26 Mw |

À 11 points, le 1,10 Mw est dominé par des prédictions précoces, avant
apprentissage. Ces chiffres documentent la méthode de notation.

## Limites

- Détecte des événements déjà produits ; pas de prévision.
- La calibration est liée au site ; déplacer la boîte impose une reconvergence.
- Un seul PGA est un proxy bruité de l’énergie ; ±0,3–0,5 en magnitude est le
  plafond réaliste.
- Nœud de mouvement fort de quartier. Pas de téléséismes.
- Il faut une région active et un catalogue publié rapidement.

## Coût (1er septembre 2026)

| Pièce | Prix | Source |
|---|---|---|
| Arduino UNO Q 2 GB (ABX00162) | 59,00 $, ou 44,00–45,20 $ | store.arduino.cc ; DigiKey, PiShop, Farnell |
| Modulino Movement (ABX00101, LSM6DSOX) | 11,80 $ | store.arduino.cc |
| Alimentation USB-C, 5 V / 3 A | ~15 $ | courant, estimation |
| **Un nœud** | **71–86 $** | ~90 $ avec taxes et port |

Un chiffre de 25 $ utilisé plus tôt dans ce projet était faux (l’UNO Q seul le
dépasse). Prix Raspberry Shake le même jour : 294,99 $ la carte, 584,99 $ clé
en main ([raspberryshake.org](https://raspberryshake.org/pricing)). Nomenclature :
[`docs/hardware.md`](docs/hardware.md).

## Géométrie multi-stations

![Une station donne un anneau ; trois anneaux se croisent](docs/images/network.png)

Le micrologiciel garde la norme du vecteur d’accélération : une station donne
une distance, pas d’azimut. La polarisation P est sous le plancher du
déclencheur. Trois stations s’intersecteraient. Chaque nœud ajusterait ses
coefficients sur le catalogue. C’est un argument géométrique. Il n’a pas été
mesuré : une station, une confirmation, zéro détection autonome.

## Lancer (sans matériel)

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml

python main.py --replay       # http://localhost:8000
python audit.py               # résidus hors échantillon
python audit.py --include-synthetic
```

Autres modes : `python main.py --mock`, `python pipeline.py --mock`,
`python main.py` (capteur). Sur la carte le dépôt est une App Lab App :

```bash
arduino-app-cli app start ~/ArduinoApps/sismo-la
arduino-app-cli app logs  ~/ArduinoApps/sismo-la
```

## Architecture

```
                     Arduino UNO Q
 ┌───────────────────────────┬────────────────────────────────┐
 │   STM32U585 (MCU)         │   Dragonwing QRB2210 (MPU)     │
 │   Zephyr RTOS, temps réel │   Debian Linux                 │
 ├───────────────────────────┼────────────────────────────────┤
 │ - IMU 100 Hz, LSM6DSOX    │ - WiFi + FDSN USGS             │
 │   Qwiic sur Wire1         │   (contexte ≥ M0,5,            │
 │ - STA/LTA 0,5 s / 10 s    │    appariements ≥ M2, 160 km)  │
 │ - PGA, durée, f0          │ - corrélation, modèles,        │
 │ - événement ──────────────┼─►  enveloppe, retro, audit     │
 │   via le Bridge           │ - tableau de bord + publish    │
 └───────────────────────────┴────────────────────────────────┘
                    USGS: https://earthquake.usgs.gov/fdsnws/event/1/
```

Le Qwiic est sur **`Wire1`**. Le `Serial` du MCU est D0/D1, pas l’USB. Le Bridge
exige des versions alignées de `arduino-router` et de la bibliothèque bridge.
Notes : [`docs/getting-started.md`](docs/getting-started.md),
[`docs/hardware.md`](docs/hardware.md).

## Publication

`python/main.py` écrit un instantané JSON (`publish:` dans `config.yaml`).
[`web-remote/`](web-remote/) l’affiche. Chiffres :
[`data.html`](web-remote/data.html). L’instantané **n’a pas de coordonnées**.
`publish.include_location: true` place la station sur la carte.

Le journal et l’état des modèles sont sur le système de fichiers hôte
(`event_log.jsonl`), hors conteneur.

## Organisation

```
sismo-la/
├── app.yaml                   # manifeste App Lab
├── python/                    # MPU Dragonwing (Debian)
│   ├── main.py                # boucles, tableau de bord, publisher
│   ├── pipeline.py            # détection / corrélation, CLI
│   ├── usgs.py                # client FDSN
│   ├── calibration.py         # modèles amplitude + distance
│   ├── classifier.py          # régression logistique en ligne
│   ├── envelope.py            # enveloppe continue, un CSV / jour UTC
│   ├── retro.py               # recherche à l’arrivée catalogue
│   ├── expected.py            # attendu vs observé
│   ├── audit.py               # score hors échantillon du journal
│   └── dashboard/index.html   # tableau de bord opérateur
├── sketch/                    # STM32U585 (Zephyr)
├── deploy/                    # sidecar watchdog
├── docs/
└── web-remote/                # GitHub Pages
```

## Liste

- [x] Nœud autonome : détecter → recouper → apprendre → publier.
- [x] Reprise après coupure (4 min 24 s).
- [x] Seuil de détection et taux attendus mesurés.
- [x] Loi d’atténuation réajustée sur 12 324 PGA ShakeMap.
- [x] Enveloppe continue + recherche rétrospective (facteur 7–8 en amplitude),
      comptée à part des détections.
- [x] Première confirmation (`ci41540608`, M3,2, 2 septembre 2026). Le
      déclencheur aveugle demandait ~3× l’amplitude arrivée.
- [ ] Première détection autonome : aucune. Calibration d’amplitude 0 sur 8.
- [x] Audit catalogue ; 0 aurait-dû-être-vu sur les 30 jours au 2 septembre.
- [ ] Courbe de calibration sur vrais enregistrements, résidus tenus de côté.
- [ ] Vidéo du concours : replay + tap en direct.

[Concours Hackster](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab),
**Best Social Impact**, clôture **13 septembre 2026**. Texte :
[`docs/hackster-story.md`](docs/hackster-story.md).

## Licence

MIT — [`LICENSE`](LICENSE).
