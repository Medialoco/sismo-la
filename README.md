# Sismo-LA — Sismographe communautaire bas coût pour Los Angeles

Nœud sismique **bas coût** basé sur l'**Arduino UNO Q**, rendu crédible par un
**auto-étalonnage continu sur le catalogue USGS**.

Projet pour le concours
[Invent the Future with Arduino UNO Q and App Lab](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab).
Catégorie visée : **Best Social Impact** (alternative : Industrial IoT).

## Idée en une phrase

Un capteur MEMS seul n'est pas un sismomètre. Mais à Los Angeles, le catalogue
USGS fournit une vérité-terrain permanente (heure, magnitude, distance). En
**corrélant** les secousses mesurées localement avec les vrais séismes **≥ M3**,
l'appareil **apprend sa propre fonction de réponse** : il devient un sismographe
utile sans matériel coûteux.

## Pourquoi c'est réaliste (et ses limites)

- **Réaliste** : détecter un séisme **M3–M4 proche** (quelques dizaines de km) avec
  un IMU type LSM6DSOX, car le pic d'accélération (PGA) local dépasse le bruit.
- **Réaliste** : étalonner amplitude ↔ magnitude/distance par régression sur les
  événements confirmés par USGS.
- **Limite assumée** : pas de détection télésismique (séismes lointains) — cela
  exige un géophone. C'est un **détecteur de mouvement fort local**, pas un
  sismomètre de recherche.
- **Précédents** : MyShake (UC Berkeley), Quake-Catcher Network, Raspberry Shake.

## Architecture des deux cerveaux

```
                Arduino UNO Q
 ┌───────────────────────────┬───────────────────────────┐
 │   STM32U585 (MCU)         │   Dragonwing QRB2210 (MPU) │
 │   temps réel              │   Debian Linux             │
 ├───────────────────────────┼───────────────────────────┤
 │ - lit l'IMU (LSM6DSOX)    │ - WiFi                     │
 │   ~100-200 Hz             │ - flux USGS (≥ M3, 160 km) │
 │ - détection STA/LTA       │ - corrélation temporelle   │
 │ - capture fenêtre + PGA   │ - étalonnage (régression)  │
 │ - émet l'événement ───────┼─► - classif. Edge Impulse  │
 │   (Bridge / Serial)       │ - dashboard web App Lab    │
 └───────────────────────────┴───────────────────────────┘
                          USGS : https://earthquake.usgs.gov/fdsnws/event/1/
```

## Matériel

- **Arduino UNO Q** (WiFi intégré).
- **IMU** : Modulino Movement (LSM6DSOX) via Qwiic, ou tout accéléromètre I²C
  compatible. *(À adapter selon la connectique réellement disponible.)*
- Alimentation USB-C.
- Optionnel : écran HDMI pour le dashboard en local.

## Structure du dépôt

```
sismo-la/
├── README.md
├── app.yaml                  # manifeste App Lab (squelette à adapter)
├── docs/
│   ├── architecture.md
│   ├── calibration.md        # le coeur de l'idée : l'étalonnage USGS
│   └── hackster-submission.md # checklist pour rester dans les clous du concours
├── firmware/seismo_mcu/
│   └── seismo_mcu.ino        # MCU : STA/LTA + émission d'événements
├── app/
│   ├── main.py               # orchestration (lit MCU, corrèle, étalonne)
│   ├── usgs.py               # client catalogue USGS (LA, ≥ M3)
│   ├── calibration.py        # modèle d'étalonnage persistant
│   ├── requirements.txt
│   └── config.example.yaml
└── web/index.html            # dashboard placeholder
```

## Démarrage rapide (développement sur PC, sans matériel)

```bash
cd app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
python main.py --mock        # simule des événements MCU + interroge USGS
```

Le mode `--mock` génère de fausses secousses pour tester la chaîne (corrélation,
étalonnage, affichage) sans l'UNO Q.

## Feuille de route

- [x] Squelette du projet + analyse de faisabilité.
- [ ] Sketch MCU STA/LTA validé sur table (tape sur la table = déclenchement).
- [ ] Pont MCU → Linux via Bridge App Lab (remplace le Serial du prototype).
- [ ] Corrélation temporelle robuste (horloge, fenêtre P/S, dérive).
- [ ] Étalonnage : accumuler des événements M3+ réels sur LA pendant quelques semaines.
- [ ] Modèle Edge Impulse séisme vs bruit (camion, porte, pas).
- [ ] Dashboard App Lab + alertes.

## Étalonnage en bref

À chaque secousse locale, on cherche un séisme USGS confirmé dans une fenêtre de
temps. Si correspondance, on ajoute le couple `(log10(PGA), magnitude, distance)`
au jeu d'étalonnage et on ré-ajuste la régression
`Mw ≈ a·log10(PGA) + b·log10(distance) + c`. Détails dans
[`docs/calibration.md`](docs/calibration.md).
