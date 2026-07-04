# Conversation d'origine — création du projet (UnoSeismo → Sismo-LA)

Cette page rapatrie l'échange Cursor fondateur du projet, initialement tenu dans
l'ancien workspace `UnoSeismo` (`~/Documents/Projets/dev/UnoSeismo`).

- Transcript source : `c74b0ee2-6bc0-42a0-8c04-16fd1f11ff70.jsonl`
- Seules les questions de l'utilisateur et les réponses de l'assistant sont
  conservées (le raisonnement interne a été retiré pour la lisibilité).

---

## 1. Idée initiale et cahier des charges

**Utilisateur :**

> J'ai un arduino Q. Je veux créer le projet suivant pour participer à ce concours :
> https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab
>
> Je voudrais qu'on équipe l'arduino de sensors pour détecter les secousses
> sismiques. Et sur l'arduino il y aurait un LLM. Et on commence à mesurer. Et on
> compare aux résultats temps réel de l'USGS
> (https://earthquake.usgs.gov/earthquakes/eventpage/ci41426384/executive) par
> exemple et ensuite on corrige et on entraîne.
>
> Analyse et aide moi à construire un périmètre. Du point de vue user : tu as
> l'appareil, tu l'allumes, il se calibre en 5 mn en comparant à USGS et ensuite
> il est calibré au moins pour cette latitude/longitude.
>
> Analyse et créé le cahier des charges, ce projet peut gagner ? Go

**Assistant :** Rédaction d'un cahier des charges complet (`SPECIFICATION.md`).
Synthèse :

- **Concept en une phrase** : « Branchez, attendez 5 minutes, et vous avez un
  sismographe calibré qui parle humain. »
- **Architecture duale** : le STM32 échantillonne l'ADXL355 en temps réel
  (STA/LTA) ; le Qualcomm fait tourner Edge Impulse + TinyLlama + le dashboard.
- **Triple couche d'IA** : Edge Impulse (classification sismique, partenaire du
  concours), TinyLlama 1.1B (rapports en langage naturel, ~940 MB RAM, ~10 tok/s),
  et l'auto-calibration USGS comme boucle d'apprentissage.
- **Catégorie Social Impact** : « sismologie citoyenne pour < 100 € ».
- **Différenciateur clé** : auto-calibration via l'API USGS (requête toutes les
  60 s, comparaison des détections, amélioration continue).
- **Limites honnêtes** : ADXL355 (MEMS) détecte M ≥ 2.5-3.0 ; LLM lent (~10 tok/s)
  mais déclenché seulement sur événement ; prévoir un simulateur de secousse pour
  la démo.
- **BOM minimal** : ~53 € hors UNO Q. Capteur clé : **ADXL355** (accéléromètre
  20 bits dédié au sismique).

---

## 2. Contexte Los Angeles

**Utilisateur :**

> L'idée c'est de l'utiliser en Californie, je suis à LA, il y a des séismes tout
> le temps.

**Assistant :** LA est un terrain de jeu idéal. Données USGS live ajoutées au spec :

- **256 séismes en une semaine** dans un rayon de 200 km (M ≥ 0.5), soit ~36/jour.
- Un **M4.1 le jour même** près de Ludlow (53 personnes l'ont ressenti, ShakeMap).
- Un **M1.2 à Lake View Terrace**, à ~15 km de downtown LA.

Conséquences : calibration quasi-instantanée, feedback loop USGS continu, risque
« pas de séisme pendant la démo » éliminé, narrative béton pour les juges.

---

## 3. Page web existante

**Utilisateur :**

> Sur mon site, voici les 5 derniers quakes à LA :
> https://benoit-prieur.fr/tools/quakes.html

**Assistant :** Atout confirmé — l'utilisateur connaît déjà l'API USGS et a une
visu fonctionnelle (code couleur par magnitude, carte autour de LA). Le client
Python pour l'UNO Q sera une traduction directe de la logique JS existante. Pour
les juges : montrer côte à côte la page web (USGS pur) et le dashboard UnoSeismo
(capteur + corrélation USGS) ; la différence = la valeur ajoutée.

---

## 4. Le paradigme généralisable

**Utilisateur :**

> L'idée ici c'est d'entraîner ou calibrer notre appareil compte tenu de sa
> latitude/longitude avec des requêtes USGS, on compare les deux mesures et on
> adapte : si on le fait 100 fois ou 10 fois ça suffit pour avoir un appareil
> calibré et autonome. Et ce serait une POC dès lors qu'un truc est mesurable et
> que de l'open data est dispo.

**Assistant :** Formalisation du paradigme dans le spec :

> **Capteur cheap (25 €) × Open data (gratuit) = Instrument calibré autonome**

- Le device **compare** sa mesure brute à la vérité terrain USGS, **construit**
  une fonction de transfert locale `f(accélération) → magnitude`, **converge** en
  10-100 itérations, puis **devient autonome** (plus besoin d'Internet).
- Estimations à LA : 10 itérations → 3-5 jours (utilisable) ; 50 → 3-4 semaines
  (bien calibré) ; 100 → 6-8 semaines (expert local, offline).
- **Généralisable** : même logique pour qualité de l'air (MQ-135 + OpenAQ), météo
  (BME280 + NOAA), bruit urbain, qualité de l'eau, radiation… Dès qu'un phénomène
  est mesurable et qu'il existe de l'open data.

---

## 5. Pré-brevet (PPA)

**Utilisateur :**

> Je pense même qu'il faudrait peut-être un pré-brevet ?

**Assistant :** Oui, un provisional patent est une bonne idée.

- **Nouveau** (aucun prior art trouvé) : la **méthode** de calibrer un capteur
  cheap via une **API open data publique** comme vérité terrain, de manière
  **itérative**, pour construire une **fonction de transfert géo-spécifique**
  rendant l'appareil **autonome après convergence**. Les brevets existants
  couvrent l'auto-calibration hardware (comparaison interne) ou la calibration
  cloud avec coefficients pré-stockés — pas la même chose.
- **Plan** : déposer un US Provisional Patent Application (~65 $ micro-entity, pas
  de claims formels) **AVANT** toute publication. Statut « Patent Pending »
  pendant 12 mois + date de priorité.
- **Ordre critique** : `Déposer le PPA → publier sur Hackster → soumettre au concours`.

---

## 6. Stratégie de publication

**Utilisateur :**

> Il faut publier sur Hackster ? Je comptais aussi une publi quelconque
> (scientifique) + pré-brevet du concept.

**Assistant :** Stratégie en 3 couches qui se renforcent :

1. **PPA (65-130 $)** — protège l'invention, se dépose en premier.
2. **Preprint arXiv (gratuit) + papier HardwareX (560 $)** — établit la priorité
   scientifique. Le concept « capteur cheap + open data API = instrument calibré
   autonome » est un vrai gap (les papiers récents utilisent la co-location avec
   des stations de référence, pas une API open data publique).
3. **Hackster** — obligatoire pour le concours (plateforme de soumission). Après
   PPA + arXiv, la soumission sera la seule avec une publication scientifique
   associée.

**Ordre critique** :
`PPA → arXiv → code → tests terrain LA → HardwareX avec résultats → Hackster`

---

## 7. Premiers livrables : preprint + liste de courses

**Utilisateur :**

> Oui, draft du preprint arXiv ? Il faut que je trouve le journal d'abord ? Puis
> commence à réfléchir à ce que j'achète, j'ai même pas le câble pour le relier.
> Puis ensuite code.

**Assistant :** arXiv est indépendant de tout journal (on poste, c'est en ligne en
24-48h, on soumet au journal séparément ou jamais). Deux livrables créés :

- **`paper/opencal_preprint.tex`** — « OpenCal: Iterative Self-Calibration of
  Low-Cost Sensors Using Public Open Data APIs as Ground Truth ». Formalise la
  méthode (Algorithm 1 : confirmed / false positive / missed), données USGS live
  de LA, tableau de généralisation. Compilable sur Overleaf (LaTeX absent en local).
- **`SHOPPING_LIST.md`** — pour démarrer : EVAL-ADXL355-PMDZ (~48 $, DigiKey),
  câble USB-C avec data (~10 $), jumper wires femelle-femelle (~6 $). Total ~64 $.
  Câblage : 6 fils (CS, MOSI, MISO, SCLK, GND, 3.3V) entre le PMOD ADXL355 et le
  header SPI de l'UNO Q. Pas de level shifter (tout en 3.3V).

**Prochaine étape proposée** : commencer le client USGS Python sur le Mac (sans
hardware), composant réutilisé dans le preprint comme validation.
