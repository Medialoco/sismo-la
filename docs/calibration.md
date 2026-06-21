# Étalonnage par le catalogue USGS

C'est le cœur du projet : transformer un capteur bon marché en instrument utile
en s'appuyant sur une vérité-terrain gratuite et permanente.

## Principe

Un séisme produit, à une station donnée, un pic d'accélération du sol (PGA) qui
décroît avec la distance et croît avec la magnitude. En première approximation
(loi d'atténuation simplifiée) :

```
log10(PGA) ≈ a·Mw + b·log10(distance) + c
```

On ne connaît pas `a, b, c` pour ce capteur particulier dans son environnement.
Mais USGS nous donne `Mw` et la position (donc la `distance` à LA) de chaque
séisme. À chaque correspondance « secousse mesurée ↔ séisme catalogué », on
obtient un triplet `(PGA_mesuré, Mw, distance)`. Avec assez de triplets, on
inverse la relation pour **estimer la magnitude** à partir du PGA mesuré :

```
Mw_estimée ≈ a'·log10(PGA) + b'·log10(distance) + c'
```

## Procédure

1. **Phase d'amorçage (au lancement)** — l'appareil interroge USGS pour les
   séismes récents ≥ M3 autour de LA et affiche l'état « non étalonné ». Tant
   qu'on n'a pas assez de points, on ne fournit qu'une magnitude indicative.

2. **Accumulation** — chaque secousse locale corrélée à un séisme USGS ajoute un
   point d'étalonnage (persisté en JSON).

3. **Ajustement** — régression linéaire (moindres carrés) sur les points
   accumulés. On garde des métriques de qualité (RMSE, nombre de points).

4. **Estimation** — une fois `N ≥ N_min` points (ex. 8–10), l'appareil estime la
   magnitude des secousses non encore présentes dans le catalogue (alerte
   précoce), puis se corrige quand USGS confirme.

## Fenêtre de corrélation

Une secousse locale est associée à un séisme USGS si :

- le séisme est **≤ 160 km** de LA et **≥ M3** ;
- l'écart temporel entre l'horodatage local et l'heure d'origine USGS est dans une
  fenêtre `[0, match_window_s]` tenant compte du temps de trajet des ondes et de
  la dérive d'horloge.

Les déclenchements locaux **sans** séisme USGS correspondant sont des candidats
« bruit » → jeu d'entraînement pour le modèle Edge Impulse.

## Robustesse

- Distance basée sur les coordonnées USGS et celles de la station (LA fixe).
- Rejet des points aberrants (résidu > k·RMSE).
- L'étalonnage est **propre au site** : déménager la station invalide l'historique
  (volontairement : on valide uniquement à Los Angeles dans ce projet).
