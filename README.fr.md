# Sismo-LA — un sismographe domestique qui apprend sur la liste officielle des séismes

[English](README.md) · [Français](README.fr.md)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22679543.svg)](https://doi.org/10.5281/zenodo.22679543)

Sismo-LA est une petite station dans une maison du comté de Los Angeles. Elle
fonctionne sur USB-C et WiFi, pour environ 80 $. Son accéléromètre MEMS — une
puce de la même famille que le capteur d'inclinaison d'un téléphone — mesure
les vibrations du sol et du bâtiment.

Le [catalogue USGS](https://earthquake.usgs.gov/) est la liste officielle des
séismes de la région. Quelques minutes après chaque événement, il publie
magnitude, lieu, profondeur et heure exacte. Au-dessus d'environ M1,5 ici, il
permet aussi d'affirmer qu'**aucun autre séisme n'a eu lieu**. C'est ce second
fait qui rend une station silencieuse vérifiable.

La station compare *ce que cette boîte a mesuré* et *ce que l'USGS rapporte*.
Une liste de détections vide admet alors trois lectures : rien n'était assez
proche ; la station est aveugle ; ou elle est arrêtée. Distinguer ces trois
cas est l'objet du projet. Les correspondances, quand elles existent,
ajusteraient un modèle propre à ce capteur, sur cette étagère, dans ce
bâtiment. Ce modèle a encore **0 point sur 8**.

Question testée :

> Un nœud de ce prix peut-il détecter un séisme et estimer sa magnitude, sans
> surveillance et sans calibration manuelle ?

**Réponse courte au 8 septembre 2026 :** pas encore pour la détection autonome.
La station n'a trouvé aucun séisme toute seule. Elle a confirmé un séisme en
relisant son enregistrement à l'heure indiquée par l'USGS, puis elle a publié
un premier cas où sa propre loi disait qu'elle aurait dû voir un séisme sans
en trouver la trace. Publier cet échec est le résultat principal.

### Comment lire ce projet

Trois questions, dans cet ordre : **que peut voir le capteur ?**, **que
s'est-il passé au moment où un séisme a eu lieu ?**, et **la station
reconnaît-elle ses propres erreurs ?**

Les nombres ci-dessous sont de trois sortes. Une **mesure** vient du capteur.
Une **prédiction** vient d'un modèle (quelle secousse un séisme du catalogue
aurait dû produire ici). Un **contrôle** est le même test, à un instant où
aucun séisme n'a eu lieu. Une **confirmation** est une mesure prise à une
seconde que l'USGS a désignée ; ce n'est pas une détection.

Page publique : <https://medialoco.github.io/sismo-la/>. Le nœud y apparaît comme
un **disque de 20 km sur la San Fernando Valley** ; sa position n’est pas
publiée. Un deuxième nœud est une autre ligne dans `web-remote/stations.json`
avec son propre fichier snapshot.

Un rapport technique sur la méthode et les résultats mesurés est publié sur
Zenodo, [10.5281/zenodo.22679543](https://doi.org/10.5281/zenodo.22679543) ; voir
[Article scientifique](#article-scientifique) plus bas.

![Le nœud : Arduino UNO Q et Modulino Movement](docs/images/station.png)

*4 septembre 2026, quelque part dans la San Fernando Valley. Arduino UNO Q et
Modulino Movement, alimentation USB-C.*

![Tableau de bord opérateur : cercles USGS, les trois modèles et l’audit](docs/images/dashboard-live.png)

*Tableau de bord opérateur, en direct, 4 septembre 2026. Les cercles sont les
événements USGS. Les trois modèles, à droite, affichent tous **learning** : 0
point de calibration sur 8, 0 point de distance, 0 séisme contre 4027 bruits. En
dessous, l’audit de la station sur 336 heures : 6 événements catalogués, 2 avec
un enregistrement à l’instant d’arrivée, 0 à portée et non vu. Le repère est un
placeholder du centre de Los Angeles ; ce tableau de bord reste sur le réseau
local et affiche la position réelle.*

## Vocabulaire

Une magnitude décrit la taille du séisme à sa source. Le PGA décrit, lui,
l'accélération reçue par cette station. Deux séismes de même magnitude peuvent
produire des PGA très différents selon leur distance, leur profondeur et le sol.
Il ne faut donc pas lire un PGA comme une magnitude, ni comparer les deux sans
indiquer la distance.

| Terme | Sens ici |
|---|---|
| **Station / nœud** | Cette boîte : Arduino UNO Q + module MEMS + alimentation + WiFi. |
| **Catalogue** | Liste officielle USGS des séismes. Il dit quels événements ont eu lieu, et au-dessus d'environ M1,5 ici, qu'aucun autre n'a eu lieu. La station n'appartient pas à ce réseau et n'y change rien. |
| **MCU** | Le microcontrôleur temps réel (STM32). Il lit le capteur 100 fois par seconde et décide du début d’une secousse. |
| **Côté Linux** | Le processeur d’application de la carte. Il parle à l’USGS, stocke, ajuste les modèles, sert le tableau de bord. |
| **PGA** | Peak ground acceleration : la plus grande accélération d’une secousse, en *g* (1 g ≈ 9,8 m/s²). Un pas dans cette maison, c’est quelques millièmes de g. |
| **STA/LTA** | Une alarme qui compare *maintenant* (0,5 s) et *d'habitude* (10 s). Quand le rapport saute, le MCU déclare un événement. Il n’y a pas de ligne fixe « tirer à 0,01 g » ; le plancher suit le bruit récent. |
| **Déclencheur aveugle** | Le STA/LTA qui tire tout seul, sans l’aide du catalogue. |
| **Enveloppe** | Une silhouette à 1 Hz du mouvement filtré (0,7–12 Hz) : un maximum et une moyenne par seconde. Un fichier CSV par jour UTC. Suffit pour *revenir* sur une seconde où le déclencheur n’a pas tiré. |
| **z** | À quel point l'enveloppe sort de l'ordinaire des minutes précédentes, en unités de la dispersion de ce site. z = 4,0 est le seuil de confirmation. |
| **Contrôle** | La même recherche, à un instant où aucun séisme n'a eu lieu. Si le seuil est encore franchi, c'est une fausse confirmation. |
| **Calibration** | Ajuster `magnitude ≈ a·log10(PGA) + b·log10(distance) + c` sur des exemples appariés. Huit correspondances avant que le modèle d’amplitude soit traité comme utilisable. Les coefficients appartiennent à cette installation. |
| **Mouvement fort** | Sensible aux secousses proches, d’échelle « ressentie ». Ce nœud n’enregistre pas les séismes lointains (téléséismes). |

### La seule échelle à retenir

Tout ce qui suit est en **mg**, un millième de *g*. Quatre nombres mesurés posent
le problème en entier :

| | amplitude | ce que c’est |
|---|---|---|
| Bruit électrique propre du capteur | **0,36 mg** | le plancher. Rien de plus faible ne sera jamais visible. |
| Seuil de déclenchement, site au repos | **3,08 mg** | 8,55 fois le bruit de cet instant. |
| Un pas d’adulte sur le plancher | **4 – 11 mg** | déclenche sans difficulté. |
| Le séisme M3,2 que la station a enregistré | **1,1 mg** | n’a jamais approché le seuil. |

Le bruit domestique dépasse le séisme enregistré d’**un facteur huit**. Le
déclencheur aveugle n’a donc jamais attrapé de séisme, et c’est un second canal,
guidé par le catalogue, qui fait ce travail.

## Deux canaux à tenir séparés

Une puce MEMS ne distingue pas un séisme d’une porte claquée. Le catalogue le
peut, donc la station regarde le sol de deux façons et tient deux comptes.

| Canal | Ce qui s’est passé | Peut entraîner le modèle d’amplitude ? |
|---|---|---|
| **Détection** | Le STA/LTA aveugle a tiré tout seul. Si l’USGS a ensuite un séisme à cette seconde, le couple (PGA, M et distance catalogue) est un exemple de calibration. | oui |
| **Confirmation** | L’USGS a publié une heure d’origine. La station a calculé quand les ondes devaient arriver et a lu l’enveloppe stockée. Si l’enveloppe est élevée (z ≥ 4), le sol a bougé. La station n’a pas trouvé cette seconde toute seule. | non |

Les confirmations sont exclues pour trois raisons distinctes. Elles sont
*sélectionnées* pour être une grande excursion près du bruit, donc leur PGA est
biaisé vers le haut, et les événements qui n'ont rien délivré ne fournissent
aucun point — l'échantillon est tronqué exactement du côté dont le modèle a
besoin. La distance est circulaire : elle vient du catalogue qui fournit aussi
la magnitude cible, et c'est elle qui localise la fenêtre où le PGA est lu. Et
ce n'est pas la même grandeur : un déclenchement mesure un pic sur 0,5 s à
95 Hz, l'enveloppe une moyenne glissante sur 5 à 20 s à 1 Hz.

La séparation est structurelle et non un réglage : aucun chemin de la boucle
rétrospective n'appelle `add_point`. Seul un déclenchement aveugle apparié au
catalogue alimente les modèles.

Le journal, le tableau de bord et la page publique tiennent deux listes.

## Déroulement d’un cycle

1. **Sentir.** Le MCU fait tourner le STA/LTA. Sur un déclenchement il envoie
   trois nombres via le Bridge de la carte : PGA, durée, fréquence dominante.
2. **Demander.** Linux interroge le FDSN USGS dans un rayon de 160 km. La carte
   montre les événements jusqu’à M0,5 ; un appariement de calibration doit être
   ≥ M2.
3. **Étiqueter.** Même seconde qu’un séisme catalogue → un couple
   d’apprentissage. Pas d’événement catalogue → un exemple de bruit (camion,
   pas).
4. **Ajuster.** Trois modèles se mettent à jour à chaque exemple. Une fois
   assez de points, ils sont stockés sur disque et tournent hors ligne.

| Modèle | Entrée → sortie | Utilisable après |
|---|---|---|
| Calibration d’amplitude | log10(PGA), log10(distance) → magnitude | 8 correspondances séisme |
| Modèle de distance | durée, fréquence dominante → distance épicentrale | 5 correspondances |
| Filtre de bruit | PGA, durée, fréquence → P(c’est un séisme) | 3 séismes + 3 bruits |

Détails : [`docs/calibration.md`](docs/calibration.md).

**Recherche rétrospective.** Indépendamment du déclencheur, la station
enregistre l’enveloppe en continu. Quand l’USGS publie une origine, elle
relit les quelques secondes où l’onde S devait arriver (quelques dizaines de
secondes plus tard, selon la distance). C’est une poignée de fenêtres par
séisme, contre environ 170 000 fenêtres STA/LTA aveugles par jour : le test
peut se placer plus près du bruit et moyenner le train d’ondes. Sur le bruit
de cette station, le gain de portée est un **facteur 7–8 en amplitude, une
unité de magnitude**.

**Le catalogue est révisé, donc la recherche le relit.** Une solution automatique
peut changer des heures ou des jours plus tard : `ci41540608` est passé de M3,36
à M3,20 au bout de 78,5 h. Une révision peut déplacer la fenêtre d’arrivée (heure,
distance, profondeur) ou le contrôle d’amplitude (magnitude), donc un verdict
peut apparaître ou disparaître. Chaque séisme du catalogue est rescanné en entier
tant que son enveloppe existe, quatorze jours. Un séisme d’abord annoncé sous M2
puis révisé au-dessus est examiné, plutôt que compté comme manqué.

## État (9 septembre 2026)

La station est autonome : alimentation propre, WiFi, pas d’ordinateur branché,
pas de shell requis. Elle publie un instantané JSON toutes les 20 minutes. Si
rien n’a changé, elle envoie quand même un heartbeat après 4 heures, pour que
la page publique distingue une nuit calme d’un publisher mort. Après un vrai
débranchement, le tableau de bord a répondu en **4 min 24 s**. Une panne de
5 h 43 min a montré le MCU redémarrant depuis sa propre flash.

**Calibration d'amplitude : 0 sur 8.** **Détections autonomes de séismes : 0.**
Un séisme catalogué a été **confirmé** dans l’enveloppe (section suivante), et un
autre a été **signalé par la station comme un séisme qu’elle aurait dû voir et
qu’elle n’a pas vu** ([le premier manqué](#le-premier-manqué-6-septembre-2026)) —
un verdict qu'une révision du catalogue a depuis retiré.

Le compteur de la station affiche désormais **2 confirmés**. Un seul est réel. Le
second, le 8 septembre au soir, est une fausse confirmation mesurée
([plus bas](#le-second-franchissement-est-une-fausse-confirmation)).

## Confirmation : `ci41540608`

Événement USGS M3,2, Ontario, Californie, 2 septembre 2026, 12:37:12 UTC.

| Grandeur | Valeur | Lecture |
|---|---|---|
| z d’enveloppe | 4,34 (seuil 4,0) | la trace était 4,34 dispersions au-dessus des minutes précédentes |
| Crête / baseline | 0,001095 g / 0,0003816 g | environ 3× le niveau calme, encore une petite accélération |
| Fenêtre / décalage | 20 s, 24 s après l’origine | 24 s est un temps de trajet S ordinaire à cette distance |
| STA/LTA aveugle | ~0,0033 g requis ; n’a pas tiré | le déclencheur voulait ~3× l’amplitude arrivée |
| Site | au repos | bruit électrique du capteur ; personne au-dessus de la boîte |
| Compteur de calibration | toujours 0 sur 8 | une confirmation n’a pas le droit de l’incrémenter |

Un événement, pas un taux, et z = 4,34 est une marge mince au-dessus de 4,0.

**À quelle fréquence le second canal se trompe, maintenant mesuré sur
l’enveloppe enregistrée.** Un taux de 1 sur 1 200 avait été calculé sur du
*bruit de capteur pur*. Cette maison produit aussi des pas, donc la même
recherche a été rejouée à 3 585 instants de **contrôle** — cinq journées UTC
complètes, des heures où aucun séisme n’a eu lieu. Le seuil z = 4,34 y est
franchi **18 % du temps, une fois sur six**. Le taux suit l’occupation : 2 à
3 % maison vide, 20 à 40 % avec quelqu’un à la maison.

Ces faux succès ont un pic médian de **10 mg** (des pas). Ce séisme culminait
à 1,095 mg, sous le seuil du déclencheur. En exigeant les deux — z ≥ 4,34
*et* un pic aussi faible — il reste **1,81 %, une sur 55**. C’est le chiffre
qui s’applique ici. Rejouée aux heures voisines du 2 septembre, la recherche
donne encore 29 % de témoins au moins aussi forts. Méthode et tableau par
journée : §10.4 du rapport.

### Le second franchissement est une fausse confirmation

Ce taux a été mesuré le 8 septembre 2026 au matin. Le soir du même jour, le canal
a franchi son seuil, et la station publie **2 confirmés** depuis. Le second ne peut
pas être réel, et le montrer ne demande aucun seuil.

Événement USGS M2,33, essaim de Johannesburg, 9 septembre 2026 01:46:03 UTC
(8 septembre, 18 h 46 heure locale).

| Grandeur | Valeur |
|---|---|
| z d'enveloppe | 4,02 pour un seuil de 4,00 — une marge de 0,02 |
| Secousse attendue, loi gelée, au repère public | **0,0108 mg** |
| Bruit électrique du capteur | 0,360 mg |
| L'attendu est donc | **33 fois sous le plancher du capteur** |
| Rms / pic enregistrés | 0,4228 mg / 1,120 mg, soit 39× et **103×** la prédiction |
| Veto d'amplitude | passé : il tolère jusqu'à 146× |
| Témoins atteignant z = 4,02 sur les 13 h précédentes | **5 %** |

Pour que ce séisme *atteigne* seulement le plancher du capteur, il faudrait une
amplification de site à près de quatre écarts-types de la dispersion de la loi. Ontario, la
confirmation qui tient, était à 2,3 et a produit 1,095 mg contre un seuil de
0,44 mg.

Le franchissement est de plus fragile. Le z de 4,02 vient de la position réelle de
la station ; rejouée depuis le repère public, à 1,4 km sur cette géométrie, la même
recherche rend **z = 3,29**. Un kilomètre déplace la fenêtre d'arrivée de quelques
secondes, et cela suffit à repasser sous le seuil.

La maison était calme à cette heure — médiane 0,378 mg, pic horaire maximal
1,16 mg — donc ce n'est pas un pas mais la gigue ordinaire de l'enveloppe sur la
fenêtre de 5 s. Son pic de 1,120 mg passe même sous le plafond resserré de 1,2 mg :
il appartient à la classe résiduelle d'une sur 55, pas à celle, grossière, d'une
sur six.

Le compteur public doit donc être lu comme **le nombre de fois où le critère a été
franchi**, non comme le nombre de séismes enregistrés. Le critère est fixe, gelé
depuis le 1er septembre, et se trompe à un taux mesuré ; rien n'a été ajusté en
réaction à cet événement.

## Plancher de bruit : le mur, c'est le capteur

**Pourquoi cela compte :** le plancher de bruit est le niveau qu'affiche
l'instrument quand rien ne bouge. Tout ce qui est plus faible reste invisible,
définitivement. Avant de chercher à améliorer la station, il faut donc savoir
*ce qui* fixe ce plancher : le bâtiment, la rue, le logiciel ou la puce.

Le 1er septembre 2026, le bruit au repos a été estimé dans **deux bandes de
fréquence indépendantes sur les mêmes dix secondes**, puis comparé à la fiche
technique du LSM6DSOX. Utiliser les mêmes dix secondes pour les deux importe :
aucun des deux chiffres ne dépend alors de la comparaison d'une nuit avec une
autre.

| Bande | Mesuré | Prédiction fiche technique | Écart |
|---|---|---|---|
| 0,7 – 12 Hz (la bande sismique) | **0,00036 g** | 0,00040 g | 10 % |
| large bande | **0,00052 g** | 0,00050 g | 4 % |

Le plancher est le **bruit électrique propre du capteur**. À 4–10 % près, cette
station est aussi silencieuse que la puce le permet.

Ce bruit est *blanc* — réparti uniformément en fréquence — et il tombe à
l'intérieur de la bande sismique, si bien que la seule bande passante qu'il
resterait à retirer est celle dont un séisme a besoin. Le filtre passe-bande a
déjà pris le facteur 1,43 disponible, et aucun filtrage supplémentaire n'abaisse
le plancher. Un seuil autonome plus bas demande une puce plus silencieuse, ou
plusieurs puces ([`docs/sensor-upgrade.md`](docs/sensor-upgrade.md)).

## Quelle taille de séisme elle peut attraper

STA/LTA compare deux moyennes, c'est donc un *rapport* : il n'existe pas de
seuil fixe exprimé en g. Ce qui est fixe, c'est le rapport entre le seuil et le
bruit que suit la moyenne longue. Deux mesures le déterminent :

- le plus petit pic qui ait jamais déclenché cette station vaut **0,0044 g**
  avant le filtre passe-bande, soit **0,00308 g (3,08 mg)** après — le filtre
  abaisse le plancher d'un facteur mesuré 1,43, et le plancher d'un détecteur à
  rapport suit ;
- le plancher au repos vaut **0,00036 g**, et c'est le bruit électrique propre
  du capteur (voir [Plancher de bruit](#plancher-de-bruit--le-mur-cest-le-capteur)).

Leur quotient vaut **8,55**, seul paramètre libre ici :

```
plancher du déclencheur = 8,55 x (niveau de l'enveloppe mesuré à cet instant)
plancher rétrospectif   = plancher du déclencheur / 7,4
```

Cette formulation est prédictive : connaissant le bruit à une seconde donnée, on
sait ce qu'il aurait fallu pour déclencher à cette seconde. Passé dans la loi de
mouvement du sol ci-dessous, ce plancher devient une **magnitude requise** à
une distance donnée (±0,45 à 1σ). Sous M3, les chiffres sont des
extrapolations :

| Magnitude requise | 10 km | 30 km | 50 km | 100 km | 160 km |
|---|---|---|---|---|---|
| Déclencheur aveugle | 3,1 | 3,9 | 4,3 | 4,9 | 5,3 |
| Recherche rétrospective | 2,1 | 2,9 | 3,3 | 3,9 | 4,3 |

Ces seuils, croisés avec les **2 016** vrais événements USGS de M ≥ 2 dans
160 km sur cinq ans — comptés depuis le repère public à l'échelle de la ville,
donc reproductibles à partir de données publiques — et la dispersion 0,39 log10
de la loi, amplification de site inconnue ×1 à ×4 :

| | séismes / an | attente moyenne | P(au moins un avant le 13 sep 2026) |
|---|---|---|---|
| Déclencheur aveugle seul | 2,0 – 9,8 | 37–184 jours | 6–28 % |
| Déclencheur + recherche rétrospective | 9,9 – 36,9 | 10–37 jours | 28–70 % |

La ligne rétrospective suppose la maison au repos (environ la moitié des
heures ici). À une heure passante, l’enveloppe erre d’environ ×4 ; à une heure
calme, ~3 %. Les fichiers d’enveloppe existent depuis le 1er septembre 2026 ;
les heures antérieures ne sont pas cherchables.

## Loi de mouvement du sol

Une **loi de mouvement du sol** prédit le PGA à partir de la magnitude et de
la distance. La station utilise la même forme algébrique à l’envers : PGA et
distance connus, estimer M. Les coefficients ont été ajustés sur **12 324
valeurs de PGA** réellement enregistrées par des stations ShakeMap USGS pendant
40 séismes du sud de la Californie (M3,03–5,51, 3–200 km, 1 006 stations) :

`log10(PGA en g) = 0,867·M − 1,740·log10(R en km) − 3,305`

dispersion 0,390 log10, R² = 0,80. Un jeu de coefficients antérieur
surestimait l’amplitude de 37,9× (environ deux unités de magnitude).

## Un silence, c’est « en panne » ou « il ne s’est rien passé » ?

Une liste de détections vide est la réponse habituelle, pas une panne à
elle seule : **96,9 %** du catalogue M ≥ 2 dans 160 km sur cinq ans tombe sous
les deux canaux (rapport, fig. 2). Pour chaque séisme catalogué, la station
(1) prédit le PGA que la loi dit qui aurait dû arriver, et (2) lit le bruit
dans lequel elle était vraiment assise à cette seconde. Cinq classes :

| Classe | Sens |
|---|---|
| Hors de portée | PGA attendu sous ce que ce site peut voir ; le cas normal |
| Marginal | près du plancher ; à ne pas traiter comme un oubli |
| Déclenché | le STA/LTA aveugle a tiré et a été apparié |
| Confirmé | enveloppe élevée à l’arrivée prédite |
| Aurait dû être vu | à portée, site assez calme, rien dans l’enregistrement → une panne |

**19 examinés, 1 confirmé, 0 aurait dû être vu** — 30 jours au 2 septembre
2026. La station continue de publier les trois mêmes comptes sur les 336
dernières heures, dans
[`station.json`](https://medialoco.github.io/sismo-la/station.json) sous
`expected.summary` : *examinés / enregistrés / manqués*. Enregistré veut dire que
l’enveloppe existe à cette seconde, pas que l’événement est confirmé.

Aucune des deux pages publiques ne les affiche. Imprimés nus, « 7 · 2 · 0 » se lit
comme une note de 2 sur 7, soit l’inverse de leur sens, et ces comptes ne sont
informatifs qu’à côté de leurs définitions. Ils restent complets dans l’instantané
que ces pages lisent. Les événements à portée restent sur le réseau local.
Méthode : [`docs/expected-vs-observed.md`](docs/expected-vs-observed.md).

### Le premier manqué, 6 septembre 2026

Ce dernier compte a quitté zéro pour la première fois. Un M3,2 survenu à
07:13:11 UTC était assez proche pour que la loi de mouvement du sol place la
secousse attendue **au-dessus des 0,44 mg** que le canal rétrospectif pouvait
atteindre à cet instant, avec plus d’une chance sur deux de l’attraper même en
supposant aucune amplification de site. L’audit a donc rendu « aurait dû être vu »
et l’a publié contre la station, sans qu’on le lui demande, 32 minutes après le
séisme. L’amplitude prédite n’est pas imprimée ici : la loi s’inverse, si bien que
ce nombre à côté de la magnitude publiée donnerait la distance, et une seconde
couronne à côté de celle du 2 septembre situerait la station.

Relire l’enregistrement dit ce qui s’est passé. L’enveloppe est continue sur toute
la fenêtre d’arrivée, sans un trou, et la trace seconde par seconde d’une minute
de part et d’autre est indiscernable de la minute précédente : le rms médian monte
de **0,5 %**, contre **6,4 %** pour l’événement confirmé, et la seconde la plus
forte des deux minutes tombe *avant* que la moindre onde ait pu arriver. Le test
de significativité a rendu **z = 2,90** pour un seuil de 4, et aucune fenêtre de
moyennage entre 2 et 30 secondes ne dépasse 3,05. La secousse n’est pas dans l’enregistrement, et la prédiction se
trouvait du côté optimiste d’une loi dont la dispersion courante entre sites vaut
un facteur 2,45.

L’unique confirmation se trouve à l’autre extrémité de la même dispersion.
Ontario, le 2 septembre, était de même magnitude à presque deux fois la distance
et a délivré **7,8 fois** l’amplitude prédite. Compton, plus proche, n’a rien
délivré au-dessus du niveau ambiant. Les deux encadrent la dispersion entre sites
avec les données de la station, et placent la confirmation unique sur sa queue
favorable.

**Le verdict a été retiré le 9 septembre, et aucune mesure n'a changé.** L'USGS a
révisé l'événement de M3,2 à **M3,07** et l'a relocalisé un peu plus profondément.
Les deux corrections abaissent l'amplitude prédite, donc la borne pessimiste de la
probabilité de détection est tombée de 0,57 à **0,432**, sous la chance sur deux
qui définit « aurait dû être vu », et la station l'a reclassé **marginal**. Son
audit affiche de nouveau zéro manqué. La relocalisation a aussi déplacé la fenêtre
d'arrivée, ce qui porte le z de 2,90 à 3,54 — toujours sous 4. L'enveloppe ne
contient toujours aucune trace de ce séisme ; ce qui a bougé est le verdict, parce
que le catalogue n'est pas une référence figée. Les comptes de l'audit sont à lire
avec leur date ; le mécanisme est décrit sous
[Recherche rétrospective](#recherche-rétrospective).

Trois façons d’afficher le manqué sur les pages publiques ont été essayées puis
abandonnées : l’indicateur d’état, qui rendait identiques un audit qui fonctionne
et un capteur mort ; une ligne légendée sur la page d’accueil ; puis les trois
comptes définis un à un sur la page de données. Chacune demandait encore un
paragraphe de définitions avant qu’un entier nu cesse d’induire en erreur. Les
comptes restent dans
[`station.json`](https://medialoco.github.io/sismo-la/station.json), complets et
horodatés, toutes les 20 minutes.

## Autres mesures

| Observation | Valeur |
|---|---|
| Taux de déclenchement après passage d’un bureau à un support plus raide | 22,6 → 3,2 événements / h (−86 %). Plancher 0,00087 → 0,00066 g (−24 %). Le couplage domine les faux déclenchements. |
| Mise sous tension → tableau de bord qui répond | 4 min 24 s. Un sidecar watchdog relance le conteneur ; App Lab l’arrête sinon une seconde après le boot. |
| Fréquence dominante (après un bug de signe : échantillon centré vs non centré) | vrais taps à 2,6 / 5,0 / 10,6 Hz. Le bug imprimait ~25 Hz sur tout signal. |
| Pic médian de l’enveloppe par jour, 1er–8 septembre | 0,721 – 0,784 mg, soit 4 % d’écart sur huit jours pleins. Sur les mêmes jours, les déclenchements aveugles vont de 0 à 3 112 et le maximum quotidien de 1,4 à 24 mg. Le nombre de déclenchements suit la présence de quelqu’un dans la maison, pas le plancher de bruit : les 4, 5 et 6 septembre n’en ont produit aucun. |

Le seul signal indépendant « le capteur est vivant » est le battement MCU
(~10 s). Un 200 du tableau de bord web veut dire que le processus Linux tourne.
`health.stale` pilote le badge public et une bannière `STATION DEGRADED`.

## Replay : un test du logiciel

`python main.py --replay` tire le vrai catalogue des 24 dernières heures et
*invente* le PGA à partir de la magnitude et de la distance via l’*ancienne*
loi (avant réajustement), donc les fausses amplitudes sont 38× trop grandes.
C’est volontaire : des valeurs corrigées resteraient sous le déclencheur et la
démo ne montrerait rien. Le calibreur ajuste alors l’inverse de cette même loi.
Les résidus du replay testent le pipeline ; ils sont circulaires et n’ont pas de
sens physique.

Le RMSE du tableau de bord est un résidu **intra-échantillon** (le modèle noté
sur des points qu’il a déjà ajustés) et on lui donne la *vraie* distance
catalogue. En direct, il n’a qu’une distance *estimée*. `python audit.py`
parcourt le journal dans l’ordre du temps et note chaque point avec le modèle
*tel qu’il était avant ce point* (hors échantillon, préquentiel) :

| Estimateur | run A (11 pts) | run B (27 pts) |
|---|---|---|
| Intra-échantillon, vraie distance (ce que le panneau montre) | 0,20 Mw | 0,18 Mw |
| Hors échantillon, vraie distance | 0,30 Mw | 0,21 Mw |
| Hors échantillon, distance estimée (chemin en direct) | 1,10 Mw | 0,26 Mw |

À 11 points, le 1,10 Mw est dominé par les premières prédictions, quand le
modèle n’avait presque aucune donnée. Le tableau documente la méthode de
notation.

## Limites

- La station rapporte des séismes déjà produits. Elle ne prévoit pas.
- Déplacer la boîte rend les coefficients faux jusqu’à un nouvel ajustement.
- Un seul PGA est un substitut bruité de l’énergie libérée. ±0,3–0,5 en
  magnitude est le plafond réaliste même avec un bon ajustement.
- Mouvement fort seulement. Pas de téléséismes.
- La méthode a besoin d’une région active et d’un catalogue publié en quelques
  minutes. Le sud de la Californie s’en rapproche.

## Coût (prix au 1er septembre 2026)

| Pièce | Prix | Source |
|---|---|---|
| Arduino UNO Q 2 GB (ABX00162) | 59,00 $, ou 44,00–45,20 $ | store.arduino.cc ; DigiKey, PiShop, Farnell |
| Modulino Movement (ABX00101, LSM6DSOX) | 11,80 $ | store.arduino.cc |
| Alimentation USB-C, 5 V / 3 A | ~15 $ | courant, estimation |
| **Un nœud** | **71–86 $** | ~90 $ avec taxes et port |

Raspberry Shake le même jour : 294,99 $ la carte, 584,99 $ clé en
main ([raspberryshake.org](https://raspberryshake.org/pricing)). Liste :
[`docs/hardware.md`](docs/hardware.md).

## Ce que trois stations ajouteraient (géométrie, pas un résultat)

![Une station donne un anneau ; trois anneaux se croisent](docs/images/network.png)

Le micrologiciel stocke la *norme* du vecteur d’accélération : la direction
est jetée. L’onde P (l’arrivée dont la polarisation pointe vers la source) est
sous ce déclencheur. Une station donne donc une **distance**, un anneau sur la
carte. Trois anneaux s’intersecteraient. Chaque nœud ajusterait encore ses
coefficients sur le catalogue. Ceci n’a pas été construit : une station, une
confirmation, zéro détection autonome.

## Lancer sans matériel

Le replay utilise le vrai catalogue et des amplitudes synthétiques (voir plus
haut).

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml

python main.py --replay       # puis http://localhost:8000
python audit.py               # résidus hors échantillon du journal
python audit.py --include-synthetic
```

`python main.py --mock` invente des secousses. `python main.py` parle à un vrai
capteur. Sur la carte, ce dossier *est* une App
[App Lab](https://docs.arduino.cc/) :

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
 │   Qwiic sur Wire1         │   (carte ≥ M0,5, appariements  │
 │ - STA/LTA 0,5 s / 10 s    │    ≥ M2, 160 km)               │
 │ - PGA, durée, f0          │ - corrélation, modèles,        │
 │ - événement ──────────────┼─►  enveloppe, retro, audit     │
 │   via le Bridge           │ - tableau de bord + publish    │
 └───────────────────────────┴────────────────────────────────┘
                    USGS: https://earthquake.usgs.gov/fdsnws/event/1/
```

Sur cette carte le connecteur Qwiic est **`Wire1`** (pas `Wire`). Le `Serial`
du MCU est les broches D0/D1, pas l’USB. Le Bridge MCU↔Linux exige des versions
alignées de `arduino-router` et de la bibliothèque bridge.
[`docs/getting-started.md`](docs/getting-started.md),
[`docs/hardware.md`](docs/hardware.md).

## Publication

`python/main.py` écrit un instantané JSON sur minuteur (`publish:` dans
`config.yaml`). [`web-remote/`](web-remote/) dessine la carte ;
[`data.html`](web-remote/data.html) sont les tableaux. L’instantané **n’a pas
de coordonnées**. `publish.include_location: true` place la station.

Tout ce qui dérive de la position de la station peut situer la maison : une
liste de distances, une liste de probabilités de détection, ou même l’ensemble
des séismes dessinés sur la carte (un disque de 160 km trace son propre bord).
Ces champs sont donc retirés ou recentrés sur `publish.map_center`, le repère à
l’échelle de la ville que la carte publie déjà. Sans ce réglage, la position
de la station est arrondie au quart de degré.

Le journal (`event_log.jsonl`) et les fichiers de modèles sont sur le disque
hôte, à côté du conteneur, et survivent aux redémarrages.

## Organisation

```
sismo-la/
├── app.yaml                   # manifeste App Lab
├── python/                    # moitié Linux (Dragonwing)
│   ├── main.py                # boucles, tableau de bord, publisher
│   ├── pipeline.py            # détection / corrélation
│   ├── usgs.py                # client catalogue USGS
│   ├── calibration.py         # modèles amplitude + distance
│   ├── classifier.py          # filtre séisme-vs-bruit
│   ├── envelope.py            # enveloppe continue (un CSV / jour UTC)
│   ├── retro.py               # retour à l’instant d’arrivée catalogue
│   ├── expected.py            # attendu vs observé
│   ├── audit.py               # score hors échantillon du journal
│   └── dashboard/index.html   # tableau de bord opérateur
├── sketch/                    # moitié MCU (STM32, Zephyr)
├── deploy/                    # watchdog qui relance le conteneur
├── docs/
└── web-remote/                # page publique sur GitHub Pages
```

## Liste

- [x] Nœud autonome : détecter → apparier à l’USGS → apprendre → publier.
- [x] Reprise après coupure (4 min 24 s).
- [x] Plancher de déclenchement et taux attendus mesurés.
- [x] Loi de mouvement du sol réajustée sur 12 324 PGA ShakeMap.
- [x] Enveloppe continue + recherche rétrospective (facteur 7–8 en amplitude),
      comptée à part des détections.
- [x] Première confirmation (`ci41540608`, M3,2, 2 septembre 2026). Le
      déclencheur aveugle demandait ~3× l’amplitude arrivée. Son taux de fausse
      confirmation est désormais mesuré sur des enregistrements réels et non sur
      du bruit simulé : une sur 55.
- [ ] Première détection autonome : aucune. Calibration d’amplitude 0 sur 8.
- [x] Audit catalogue ; 0 aurait-dû-être-vu sur les 30 jours au 2 septembre, puis
      un premier manqué le 6 septembre, publié par la station contre elle-même,
      puis retiré le 9 par une révision du catalogue.
- [ ] Courbe de calibration sur vrais enregistrements, résidus tenus de côté.
- [ ] Vidéo du concours : replay + un tap en direct sur la boîte (vers le
      8 septembre 2026).
- [x] Rapport technique déposé sur Zenodo, [10.5281/zenodo.22679543](https://doi.org/10.5281/zenodo.22679543) (9 septembre 2026).

Candidature
[Invent the Future with Arduino UNO Q and App Lab](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab),
**Best Social Impact**, clôture **13 septembre 2026**. Storyboard vidéo :
[`docs/hackster-story.md`](docs/hackster-story.md).

## Article scientifique

Un rapport technique expose la méthode et les résultats mesurés en détail. Le
dépôt Zenodo contient les deux versions, anglaise et française, à parité complète
— mêmes sections, mêmes figures, mêmes chiffres — ainsi que l'archive qui
reproduit chaque figure et chaque chiffre depuis les enveloppes brutes de la
station. Le titre du dépôt est l'anglais, le français y figure en titre alternatif.

> Prieur, B. (2026). *Can a seismic station built on a $12 motion sensor be
> falsifiable? Measured sensitivity, retrospective channel, and continuous
> self-audit of a MEMS station in Los Angeles.* Zenodo.
> <https://doi.org/10.5281/zenodo.22679543>
>
> ORCID : [0000-0003-0786-0049](https://orcid.org/0000-0003-0786-0049).

Ce rapport ne reprend pas ce README. Il pose une question plus étroite — une
station à ce prix peut-elle publier, sans intervention, de quoi permettre à un
tiers d'établir qu'elle s'est trompée ? — et y répond avec cinq figures et les
chiffres qui les sous-tendent :

- le plancher de bruit mesuré dans deux bandes de fréquence, à 4–10 % de la fiche
  technique du capteur, ce qui établit que la limite est la puce elle-même ;
- le seuil de déclenchement à 8,55 fois le bruit ambiant instantané, et les
  magnitudes qui s'en déduisent par distance ;
- le gain du canal rétrospectif, exactement une unité de magnitude (facteur 7,4) ;
- la confirmation du 2 septembre, reproduite depuis l'enveloppe brute ;
- le taux de fausse confirmation mesuré sur 3 585 fenêtres témoins : une sur six
  pour la significativité seule, une sur 55 avec la condition d'amplitude — et le
  cas réel du 8 septembre au soir, où le canal a franchi son seuil sur un séisme
  trente-trois fois sous le plancher du capteur ;
- l'audit contre le catalogue en six verdicts, qui a produit son premier manqué
  contre la station le 6 septembre, puis l'a retiré le 9 sur révision du
  catalogue ;
- quatre affirmations de cette documentation que les données ont corrigées.

Ses figures et ses vérifications numériques sont produites par un script unique
qui **importe l'estimateur de ce dépôt** au lieu de le réimplémenter : la
vérification porte donc sur le code que la station exécute réellement. Entrées :
l'enveloppe brute de la station, cinq journées UTC complètes d'enveloppe, une requête
au catalogue de l'USGS et l'instantané public.

## Licence

MIT — [`LICENSE`](LICENSE).
