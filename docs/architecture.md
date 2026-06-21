# Architecture technique

## Vue d'ensemble

L'UNO Q est exploité comme un système hétérogène à deux processeurs qui
communiquent via le Bridge Arduino (RPC) :

- **MCU STM32U585** : tâche temps réel, déterministe. Échantillonnage de l'IMU et
  détection d'événement. C'est lui qui « ne rate pas une secousse ».
- **MPU Dragonwing (Debian)** : tâches haut niveau non temps réel — réseau,
  corrélation, étalonnage, IA, interface web.

## Chaîne de traitement

1. **Acquisition (MCU)** — lecture de l'accélération 3 axes à fréquence fixe
   (cible 100–200 Hz). On retire la gravité en suivant une moyenne lente, et on
   travaille sur la norme du vecteur d'accélération dynamique.

2. **Détection STA/LTA (MCU)** — algorithme standard en sismologie :
   - `STA` = moyenne court terme (ex. 0,5 s) de l'énergie du signal.
   - `LTA` = moyenne long terme (ex. 10 s).
   - Déclenchement quand `STA/LTA > seuil_on` (ex. 4), fin quand `< seuil_off`
     (ex. 1,5). Cela s'adapte automatiquement au bruit de fond ambiant.

3. **Caractérisation de l'événement (MCU)** — sur la fenêtre déclenchée :
   `PGA` (pic d'accélération, en g), durée, fréquence dominante approx. (comptage
   de passages par zéro). Émission d'un message d'événement compact.

4. **Transport MCU → MPU** — en production : **Bridge App Lab (RPC)**. Pour le
   prototype et le dev sur PC : lignes **JSON sur le port série**. Le code Python
   lit une abstraction « source d'événements » pour que les deux marchent.

5. **Corrélation USGS (MPU)** — pour chaque événement local, recherche d'un séisme
   USGS **≥ M3** dans un rayon de 160 km autour de LA et dans une fenêtre
   temporelle (cf. note horloge ci-dessous). Une correspondance = un point
   d'étalonnage de confiance.

6. **Étalonnage (MPU)** — mise à jour de la régression amplitude → magnitude
   (voir `calibration.md`). Persisté sur disque pour survivre aux redémarrages.

7. **Classification (MPU, Edge Impulse)** — un modèle léger classe la fenêtre
   d'événement : `seisme` vs `bruit` (camion, porte, pas...). Réduit les faux
   positifs intrinsèques au MEMS bas coût.

8. **Restitution (MPU)** — dashboard web (brick App Lab) : accélération live,
   événements locaux, séismes USGS récents, état d'étalonnage, magnitude estimée.

## Note sur la synchronisation temporelle

C'est le point délicat. Le MCU n'a pas l'heure absolue ; le MPU oui (NTP via
WiFi). Stratégie :

- Le MPU horodate la réception de chaque événement MCU (latence Bridge faible et
  bornée).
- La fenêtre de corrélation doit absorber : latence de propagation des ondes
  sismiques (P/S, plusieurs secondes selon la distance), dérive d'horloge, et
  délai de publication USGS (souvent quelques minutes). On corrèle donc **a
  posteriori** sur l'historique récent, pas en temps réel strict.

## Choix « bas coût » assumés

- Un seul IMM I²C, pas de chaîne d'acquisition analogique dédiée.
- Pas de mise à niveau / nivellement précis : la norme du vecteur dynamique rend
  la détection insensible à l'orientation.
- L'intelligence est logicielle (STA/LTA + étalonnage + IA), pas dans le capteur.
