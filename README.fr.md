# Sismo-LA — un quartier peut-il tenir son propre réseau sismique ?

[English](README.md) · [Français](README.fr.md)

Près de dix millions de personnes vivent dans le comté de Los Angeles, sur
certaines des failles les plus actives du monde. La région est déjà densément
instrumentée — des centaines de stations professionnelles, et un catalogue USGS
qui publie magnitude, lieu et profondeur en quelques minutes après chaque
événement. Presque aucun de ces appareils n’est chez quelqu’un. Les instruments
qui comptent appartiennent à des institutions, sont implantés par des
institutions, et sont calibrés par des institutions.

Supposons qu’un nœud coûte 80 $. Le reste d’un réseau de quartier est simple —
des hôtes, le WiFi, une carte. Le dur, c’est le préalable :

> **Un nœud aussi bon marché peut-il détecter un séisme et lui mettre un
> chiffre, sans surveillance, sans que personne ne le calibre jamais ?**

Ce dépôt est un nœud qui répond à cette question à Los Angeles : fonctionnement
continu sur du vrai matériel, et un compte rendu honnête de jusqu’où ça va.
Poser la question plutôt qu’affirmer la réponse est volontaire. Ça rend le
projet falsifiable, et le résultat partiel fait partie du résultat.

**Où on en est, 2 septembre 2026.** La moitié autonome est faite : la station
tourne sur sa propre alimentation, sans shell et sans ordinateur branché,
détecte les secousses, les recoupe avec l’USGS, publie un instantané toutes les
20 minutes, et est revenue seule après une vraie coupure de courant. Et le
2 septembre elle a **confirmé un vrai séisme pour la première fois** — un M3,2
près d’Ontario, Californie, nettement au-dessus de son propre bruit dans son
propre enregistrement continu, à l’instant où le catalogue disait que les ondes
devaient arriver.

Elle n’a pas *remarqué* ce séisme. Le déclencheur aveugle n’a pas tiré et ne
pouvait pas : il lui fallait environ trois fois l’amplitude arrivée. Le
catalogue a fourni la seconde à examiner et la station est retournée regarder.
Donc la moitié mesure reste ouverte sur les deux points qui comptent — **le
détecteur autonome n’a rien attrapé, et la calibration d’amplitude est toujours
à 0 des 8 correspondances** dont elle a besoin, parce qu’une confirmation n’a
volontairement pas le droit de l’alimenter. Ce qui a changé cette semaine, c’est
que l’écart a cessé d’être un mystère : le seuil de détection est maintenant
mesuré, et le mesurer a montré que ce qui retenait la station n’était pas le
capteur mais le coût de regarder à l’aveugle. Demander au catalogue *quand*
regarder vaut une unité de magnitude entière, et ça a fait passer la chance de
ressentir un vrai séisme avant la date limite de 6–28 % à 28–70 %. Dans la
journée où ce canal a été mis en service, il a renvoyé le premier vrai séisme
de l’histoire de la station — un événement, qui est une preuve d’existence et
pas un taux.

![Tableau de bord Sismo-LA — estimations de l’appareil en rouge vs vérité USGS](docs/images/dashboard-replay.png)

*Le tableau de bord opérateur. À gauche, les événements USGS en cercles
colorés — le corrigé ; les estimations de l’appareil en rouge. À droite, les
trois modèles qui apprennent. Les chiffres de cette capture viennent du mode
replay, dont les amplitudes sont synthétiques et 38× trop grandes par
construction ; elles mesurent le logiciel, pas le capteur ;
[voir plus bas](#ce-qui-est-établi-et-ce-qui-ne-lest-pas).*

## Ce que coûte un nœud

Prix relevés le 1er septembre 2026.

| Pièce | Prix | Source |
|---|---|---|
| Arduino UNO Q 2 GB (ABX00162) | 59,00 $, ou 44,00–45,20 $ | store.arduino.cc ; DigiKey, PiShop, Farnell |
| Modulino Movement (ABX00101, LSM6DSOX) | 11,80 $ | store.arduino.cc |
| Alimentation USB-C, 5 V / 3 A | ~15 $ | courant, estimation |
| **Un nœud** | **71–86 $** | ~90 $ avec taxes et port |

Donc : **75–90 $ le nœud, pas 25 $.** Toute affirmation antérieure de 25 $ dans
ce projet était non étayée et est retirée ; l’UNO Q seul coûte plus que ça.

L’argument survit facilement à la correction. Une station de recherche, une fois
implantée, installée et maintenue, est un objet à cinq chiffres — deux ordres
de grandeur au-dessus. L’instrument citoyen le moins cher avec un prix public
est un Raspberry Shake, 294,99 $ la carte et 584,99 $ clé en main
([raspberryshake.org](https://raspberryshake.org/pricing), même date). Et la
pièce qui mesure vraiment le sol ici — le module MEMS — est à 11,80 $. L’essentiel
du coût d’un nœud, c’est l’ordinateur qui apprend, pas le capteur qui sent.

Nomenclature complète dans [`docs/hardware.md`](docs/hardware.md).

## Pourquoi un nœud bon marché peut être calibré

Un accéléromètre MEMS sent le sol bouger mais n’a aucune idée de la taille du
séisme. Il n’est pas calibré, et calibrer un instrument sismique demande
d’habitude une table vibrante ou une station professionnelle à côté.

À Los Angeles, il ne faut ni l’une ni l’autre, parce que le corrigé est gratuit
et arrive en quelques minutes.

![Comment Sismo-LA se calibre : le capteur mesure une secousse, le catalogue USGS dit ce que c’était vraiment, apparier les deux dans le temps produit un exemple étiqueté, et ajuster ces exemples permet à la station d’estimer magnitude et distance toute seule](docs/images/how-it-works.png)

1. Le capteur sent une secousse, réduite à trois nombres : accélération de
   crête, durée, fréquence dominante.
2. Le côté Linux demande au catalogue USGS si un vrai séisme vient d’avoir lieu
   à proximité.
3. **Correspondance** → ce couple (ce que j’ai mesuré ↔ ce que c’était vraiment)
   est un exemple d’apprentissage. **Pas de correspondance** → c’était un
   camion, ce qui est aussi un exemple d’apprentissage.
4. Trois modèles se réajustent sur chaque exemple. Personne n’étiquette rien à
   la main.
5. Une fois convergés, les modèles vivent sur le disque et tournent le réseau
   débranché.

| Modèle | Entrée → sortie | Utilisable après |
|---|---|---|
| Calibration d’amplitude | log10(PGA), log10(distance) → magnitude | 8 correspondances |
| Modèle de distance | durée, fréquence dominante → distance épicentrale | 5 correspondances |
| Filtre de bruit | PGA, durée, fréquence → P(vrai séisme) | 3 de chaque classe |

Le modèle d’amplitude est une équation de mouvement du sol ajustée à l’envers,
`M ≈ a·log10(PGA) + b·log10(R) + c`. Ses coefficients ne sont pas des constantes
universelles : ils absorbent ce capteur, ce montage, ce bâtiment, ce sol. C’est
le but — aucun laboratoire n’aurait pu calibrer *cette* installation, et un
réseau de celles-ci n’aurait besoin d’aucun laboratoire non plus. Détails dans
[`docs/calibration.md`](docs/calibration.md).

## Ce qui s’est vraiment passé quand on l’a fait tourner

Cinq épisodes du journal, choisis parce qu’ils disent quelque chose sur le
déploiement chez les gens.

**Déplacer la boîte a coupé les faux déclenchements de 86 %, sans changer une
ligne de code.** Sortie du bureau et posée sur un meilleur support, le taux de
déclenchement est passé de 22,6 à 3,2 par heure alors que le plancher de bruit
a à peine bougé (0,00087 → 0,00066 g, −24 %). C’est le couplage, pas le
micrologiciel, qui décide si un nœud domestique est utilisable — et l’observable
à donner à un propriétaire, c’est le taux de déclenchement sur le tableau de
bord, qui répond de près d’un ordre de grandeur, pas le plancher de bruit, qui
ne le fait pas.

**Une coupure de courant, et la station est revenue seule.** Docker démarre le
conteneur au boot, puis le démon App Lab l’arrête une seconde plus tard parce
qu’il n’a pas la notion d’une appli qui devrait encore tourner — ce qui marque
aussi l’arrêt comme volontaire, donc le boot suivant n’essaie même pas. Un
sidecar watchdog la récupère : **4 min 24 s de la mise sous tension à un
tableau de bord qui sert**, vérifié sur un vrai débranchement. Une panne plus
tardive de 5 h 43 min a confirmé que le microcontrôleur redémarre dans sa
propre flash, sans aide.

**La station est devenue aveugle, et rien ne l’a dit.** Le MCU s’est arrêté ;
le rafraîchissement USGS vivait dans la boucle d’événements, donc le pipeline
s’est figé pendant que le serveur web continuait de servir un instantané vieux
de plusieurs heures comme s’il était en direct. Tous les signaux de vie que
nous avions dérivaient de la chose qui était morte. Il y a maintenant un bloc
`health` bâti sur le seul signal indépendant — le battement du MCU — affiché
en badge rouge sur la page publique et en bannière `STATION DEGRADED` sur le
tableau de bord.

**Une fonctionnalité a été fausse pendant des semaines.** L’estimation de
fréquence dominante comparait le signe d’un échantillon *centré* à celui d’un
échantillon *non centré*, sur une magnitude vectorielle qui n’est jamais
négative, donc elle rapportait ~25 Hz quoi que fasse le sol. Le replay l’a
caché, parce que le replay synthétise ce champ de façon analytique. De vrais
taps donnent maintenant 2,6 / 5,0 / 10,6 Hz.

**Notre loi d’atténuation avait tort d’un facteur 38.** Contrôlée contre
**12 324 valeurs de PGA réellement enregistrées par des stations ShakeMap
USGS** pendant 40 séismes du sud de la Californie (M3,03–5,51, 3–200 km,
1 006 stations), la loi utilisée par ce dépôt surestimait le mouvement du sol
de 37,9×, uniformément en magnitude et en distance. Réajuster la même forme
donne `0,867·M − 1,740·log10 R − 3,305`, dispersion 0,390 log10, R² = 0,80.
Chaque affirmation « ce qu’il pourrait sentir » faite avant ce contrôle était
optimiste d’environ deux unités de magnitude.

## Ce qui est établi, et ce qui ne l’est pas

**Établi.** La station est autonome : WiFi, sa propre alimentation, pas de
shell, pas d’ordinateur branché ; elle détecte, recoupe, apprend, sert un
tableau de bord, publie sur GitHub Pages toutes les 20 minutes, et se remet
d’une coupure de courant. Toute la chaîne d’apprentissage tourne de bout en
bout et converge. Chaque détection est journalisée avec ce que chaque modèle
prédissait *avant* d’apprendre ce point, donc le projet peut se noter hors
échantillon au lieu de citer des résidus d’entraînement.

**Établi le 2 septembre : ce capteur peut mesurer un vrai séisme.** Un
événement régional s’est détaché de son propre bruit dans son propre
enregistrement, à l’instant d’arrivée qu’implique le catalogue. C’est la
première preuve dure qu’un nœud à 80 $ enregistre du tout le mouvement du sol
d’un vrai séisme, et c’est tout ce que cet unique événement prouve.

**Pas établi : qu’il peut en trouver un tout seul, ou en dimensionner un.** Le
déclencheur aveugle n’a tiré que sur du bruit local, et il lui aurait fallu
trois fois l’amplitude pour tirer sur ce séisme. La calibration est toujours
à zéro sur huit, et c’est correct plutôt qu’un bug : une confirmation est
sélectionnée pour être une grande excursion près du bruit, donc son amplitude
est biaisée vers le haut par la sélection elle-même, et ajuster une loi de
magnitude sur de tels points cuirait ce biais. Ni l’un ni l’autre n’est un
échec de corrélation — c’est le seuil.

*Les chiffres du replay mesurent le logiciel, pas l’instrument.* En `--replay`
les lectures sont synthétisées à partir de la magnitude et de la distance
cataloguées via la loi d’avant le réajustement ci-dessus, donc ses amplitudes
sont 38× trop grandes — gardées volontairement, puisque des amplitudes
corrigées resteraient sous le plancher du déclencheur et la démo ne montrerait
rien — et la calibration ajuste alors l’inverse de cette même loi. Ça prouve
que le pipeline est correct et stable ; c’est circulaire par construction et
ses amplitudes ne sont pas physiques. Le RMSE du tableau de bord est pire que
ça : un résidu d’entraînement intra-échantillon calculé avec la *vraie*
distance catalogue, alors que le fonctionnement en direct lui donne une
distance *estimée*. `python audit.py` rejoue le journal pour de vrais résidus
hors échantillon :

| Estimateur | run A (11 pts) | run B (27 pts) |
|---|---|---|
| Intra-échantillon, vraie distance — *ce que le panneau montre* | 0,20 Mw | 0,18 Mw |
| Hors échantillon, vraie distance | 0,30 Mw | 0,21 Mw |
| Hors échantillon, distance **estimée** — le chemin opérationnel | 1,10 Mw | 0,26 Mw |

Le hors échantillon est systématiquement pire que le panneau, ce qui est le
sens attendu. Mais 1,10 contre 0,26 pour le même code n’est pas une mesure :
à dix points, le score préquentiel est dominé par des prédictions faites avec
un modèle qui n’avait presque rien appris. **L’instabilité est le résultat.**
Ces chiffres montrent la méthode, pas une précision.

**Le seuil de détection, mesuré.** Il n’y a pas de seuil en g absolu dans le
micrologiciel — seulement un rapport STA/LTA — donc le plancher est une
propriété du site, et il a fallu le mesurer plutôt que le chercher dans une
fiche. Sur 163 événements, la plus petite accélération de crête qui ait jamais
déclenché est **0,0034 g**, 0,0044 g dans la fenêtre la plus calme. Via la loi
réajustée, ce plancher devient une magnitude requise, ±0,45 (1σ) ; sous M3
c’est une extrapolation :

| | 10 km | 30 km | 50 km | 100 km | 160 km |
|---|---|---|---|---|---|
| Le déclencheur aveugle a besoin de | 3,1 | 3,9 | 4,3 | 4,9 | 5,3 |
| La recherche rétrospective a besoin de | 2,1 | 2,9 | 3,3 | 3,9 | 4,3 |

Croisé avec le vrai catalogue — 2 185 événements de M ≥ 2 dans un rayon de
160 km sur cinq ans — et en convertissant la dispersion de 0,39 log10 en une
probabilité par événement, le déclencheur aveugle seul devrait voir **2,0 à
9,8 vrais séismes par an** (la fourchette est l’amplification de site inconnue,
×1 à ×4). C’est une attente moyenne de 37 à 184 jours pour **un** des 8 points
dont il a besoin, et **6 à 28 %** de chances d’un premier avant le 13 septembre.
La station n’attend pas « un séisme » ; elle attend l’un d’une poignée de
séismes précis.

**C’est pourquoi le déclencheur a cessé d’être la seule entrée.** Un détecteur
aveugle doit avoir raison sur environ 170 000 fenêtres par jour, et c’est ça
qui force son seuil si loin au-dessus du bruit — pas le capteur. Mais l’USGS
publie l’heure d’origine de chaque séisme, donc la station enregistre aussi
une enveloppe continue du mouvement du sol et retourne regarder l’instant où
les ondes doivent être arrivées. Une poignée de fenêtres par séisme au lieu de
170 000 par jour achète la même confiance beaucoup plus près du bruit, et le
test peut moyenner sur tout le train d’ondes au lieu de réagir en une demi-seconde.
Mesuré sur le propre bruit de cette station : **un facteur 7 à 8 en amplitude,
une unité de magnitude entière** — cinq fois ce que valait le passe-bande
sismique, sans matériel et sans argent.

| | séismes ressentis par an | attente moyenne | avant le 13 septembre |
|---|---|---|---|
| Déclencheur aveugle seulement | 2,0 – 9,8 | 37–184 jours | 6–28 % |
| **Plus recherche rétrospective** | **9,9 – 36,9** | **10–37 jours** | **28–70 %** |

**Dans la journée où ça a été mis en service, ça en a trouvé un :
`ci41540608`, M3,2 près d’Ontario, Californie, 2 septembre 2026 à 12:37:12
UTC.** L’enveloppe enregistrée se tenait 4,34 dispersions locales au-dessus du
bruit des minutes précédentes, crête 0,001095 g contre une baseline de
0,0003816 g, dans une fenêtre de 20 s, 24 s après l’heure d’origine. Trois
choses valent plus que le résultat lui-même :

- **Le décalage le corrobore indépendamment.** 24 s après l’origine, c’est une
  arrivée d’onde S ordinaire, et le test de significativité ne regarde jamais
  le décalage — il demande seulement si l’enveloppe était élevée dans la
  fenêtre physiquement permise. Donc le timing est une preuve que la recherche
  n’a pas fabriquée.
- **Le déclencheur aveugle était court d’un facteur trois.** Il fallait environ
  0,0033 g et 0,0011 g est arrivé. Ce n’est pas un événement que le code
  précédent aurait aussi attrapé ; c’est ce que le second canal a acheté,
  mesuré sur un vrai séisme plutôt que simulé.
- **Le site était au repos**, à la propre ligne de bruit électrique du capteur,
  donc personne ne marchait au-dessus de la boîte. Le même séisme arrivé à une
  heure passante aurait été invisible — c’est la réserve du tableau ci-dessus,
  vue de l’autre côté.

À lire comme un point, pas un taux. z = 4,34 contre un seuil de 4,0 est une
marge modeste ; le taux de fausse confirmation de 1 sur 1 200 a été calculé
contre du *bruit de capteur pur*, et ce site produit ses propres impulsions,
donc ce chiffre est optimiste jusqu’à ce qu’on le recalcule sur l’enveloppe
enregistrée ; et le compteur de calibration n’a pas bougé, exprès.

**Et les deux ne sont pas la même affirmation, donc ce dépôt ne les fusionne
jamais.** Une secousse sur laquelle la station a déclenché toute seule est une
détection. Une secousse trouvée parce que le catalogue a dit quelle seconde
examiner est une *confirmation* — vraie preuve que le sol a bougé, mais la
station ne l’a pas trouvée sans aide. Le journal étiquette chaque enregistrement,
le tableau de bord et la page publique montrent deux catégories, et le compte
0 sur 8 de la calibration n’admet que le premier type. La distinction est ce
qui rend l’approche défendable ; l’effacer rendrait les chiffres un mensonge.

Deux limites voyagent avec ces chiffres. Le seuil rétrospectif n’est atteignable
que lorsque le site est au repos — mesuré, l’enveloppe erre d’un facteur 4 à
une heure passante et de 3 % à une heure calme — et ce site est au repos à peu
près la moitié du temps, ce que le tableau ci-dessus suppose. Et la recherche
ne peut pas remonter avant son installation : la station n’a gardé aucun
enregistrement continu avant le 1er septembre, seulement les secousses qui
passaient le déclencheur, précisément les mauvaises.

**Une station qui sait ce qu’elle rate.** Une liste de détections vide est un
résultat ambigu : ça peut vouloir dire un catalogue calme ou une station qui a
arrêté de marcher, et jusqu’ici rien ici ne pouvait les distinguer. La station
s’audite maintenant contre le catalogue. Pour chaque séisme catalogué elle
calcule ce que la loi réajustée dit qui aurait dû arriver ici — c’est une
*prédiction* — et lit le bruit dans lequel elle était réellement assise à cet
instant dans son propre enregistrement continu — c’est une *mesure*, et c’est
ce qui garde l’audit honnête, parce qu’un séisme arrivé pendant que quelqu’un
passait devant le capteur n’était pas détectable et l’outil doit le dire au
lieu de signaler une panne. Chaque événement tombe alors dans l’une de cinq
catégories, et une seule est un problème : **hors de portée** (normal, 99 % de
ce catalogue), **marginal**, **déclenché**, **confirmé**, ou **aurait dû être
vu et ne l’a pas été**. Sur les 30 jours au 2 septembre : **19 événements
catalogués, 1 confirmé, et 0 dans la dernière catégorie** — donc le silence
est le catalogue et pas une panne. Ces trois comptes sont tout ce que l’audit
publie ; quels événements étaient à portée est une distance épicentrale
déguisée et reste sur le réseau de la station. Méthode, validation contre les
chiffres publiés, et l’argument de confidentialité, dans
[`docs/expected-vs-observed.md`](docs/expected-vs-observed.md).

Autres limites, brièvement : ça **détecte, ça ne prédit pas** — ça ne dit rien
sur les séismes qui n’ont pas eu lieu. La calibration appartient à un endroit ;
déplacez la boîte et elle doit reconverger. Un seul PGA est un proxy bruité de
l’énergie libérée, donc ±0,3–0,5 en magnitude est le plafond réaliste. C’est
un nœud de mouvement fort de quartier, pas un observatoire large bande : pas
de téléséismes. Et la méthode a besoin d’une région active avec un catalogue
publié rapidement — le sud de la Californie est proche du cas idéal.

## Ce que trois de ceux-ci ajouteraient

![Une station mesure une distance mais pas d’azimut, donc elle ne peut placer l’épicentre que quelque part sur un anneau ; trois stations produisent trois anneaux qui se croisent en un seul point](docs/images/network.png)

Une station retrouve une distance et pas d’azimut. Le micrologiciel réduit
chaque échantillon à la magnitude du vecteur d’accélération, ce qui jette la
direction, et l’onde P — la seule arrivée dont la polarisation pointe vers la
source — est très en dessous des centièmes de g qu’il faut pour faire basculer
ce capteur. Donc la sortie honnête d’une station est un anneau. Trois anneaux
se croisent en un endroit, comme le GPS localise un récepteur dont aucun
satellite ne connaît la direction.

Ce qui rendrait un tel réseau installable, ce n’est pas le prix du capteur,
c’est que personne n’a à le calibrer : chaque nœud ajuste ses propres
coefficients contre le catalogue et s’adapte à son propre sol, bâtiment et
montage. **C’est un argument de géométrie, pas une démonstration.** Il y a une
station ; elle a confirmé un séisme et n’en a déclenché aucun, et rien dans
cette figure n’a été mesuré ni simulé.

## Le faire tourner en deux minutes

Pas besoin de matériel. Le mode replay tire le vrai catalogue des dernières
24 heures et entraîne tout le pipeline avec, sur des amplitudes synthétiques
qui ne sont pas physiques.

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml

python main.py --replay       # puis ouvrir http://localhost:8000
```

Regardez le panneau : le modèle d’amplitude passe à *calibrated*, le modèle de
distance à *ready*, le filtre de bruit commence à distinguer les séismes des
camions.

![La calibration qui converge : le panneau passe de learning 1/8 à calibrated pendant que les estimations rouges de l’appareil remplissent la carte](docs/video/calibration-timelapse.gif)

Puis notez-le honnêtement, sur le journal plutôt que sur le panneau :

```bash
python audit.py                      # résidus hors échantillon
python audit.py --include-synthetic  # noter aussi les événements --replay (circulaire)
```

Autres modes : `python main.py --mock` (secousses synthétiques),
`python pipeline.py --mock` (sans interface), `python main.py` (vrai capteur).
Sur la carte c’est une commande, parce que le dépôt *est* une App Lab App :

```bash
arduino-app-cli app start ~/ArduinoApps/sismo-la    # compile, flashe, lance les deux
arduino-app-cli app logs  ~/ArduinoApps/sismo-la    # les deux moitiés, entrelacées
```

## Dans le nœud

```
                     Arduino UNO Q
 ┌───────────────────────────┬────────────────────────────────┐
 │   STM32U585 (MCU)         │   Dragonwing QRB2210 (MPU)     │
 │   Zephyr RTOS, temps réel │   Debian Linux                 │
 ├───────────────────────────┼────────────────────────────────┤
 │ - lit l’IMU à 100 Hz      │ - WiFi + flux FDSN USGS        │
 │   (LSM6DSOX via Qwiic,    │   (contexte ≥ M0,5,            │
 │    bus Wire1)             │    correspondances ≥ M2,       │
 │ - déclencheur STA/LTA     │    160 km)                     │
 │ - PGA, durée, fréquence   │ - corrélation temporelle       │
 │   dominante par événement │ - calibration + modèle de      │
 │ - un événement ───────────┼─►  distance                    │
 │   via le Bridge           │ - filtre de bruit (régression  │
 │                           │   logistique en ligne)         │
 │                           │ - tableau de bord Leaflet +    │
 │                           │   publication                  │
 └───────────────────────────┴────────────────────────────────┘
                    USGS: https://earthquake.usgs.gov/fdsnws/event/1/
```

Le MCU fait tourner le STA/LTA, le déclencheur que les réseaux sismiques
utilisent depuis des décennies : une moyenne de 0,5 s de l’énergie du signal
contre une moyenne de 10 s, la moyenne longue étant gelée pendant un événement
pour que le séisme ne contamine pas son propre plancher de bruit. Matériel :
un UNO Q, un Modulino Movement sur le connecteur Qwiic, et une alimentation
5 V / 3 A — pas de plaque d’essai, pas de soudure. Le montage compte plus que
le capteur ; voir [`docs/hardware.md`](docs/hardware.md).

Pièges UNO Q qui nous ont coûté des jours, écrits dans
[`docs/getting-started.md`](docs/getting-started.md) : le connecteur Qwiic est
sur **`Wire1`**, le `Serial` du MCU va aux broches D0/D1 plutôt qu’à l’USB, et
le Bridge MCU↔Linux exige que le `arduino-router` de la carte et la bibliothèque
bridge soient à la même version.

## Fonctionnement autonome

La station a besoin du WiFi et d’une alimentation USB-C, rien d’autre.
`python/main.py` pousse un instantané JSON sur un minuteur (bloc `publish:`
dans `config.yaml` : HTTP POST, écriture de fichier, ou n’importe quelle
commande d’envoi), et [`web-remote/`](web-remote/) le lit — une carte, et
[`data.html`](web-remote/data.html) pour les chiffres derrière, y compris
chaque secousse qui n’était qu’un camion de passage. Publié sur
**<https://medialoco.github.io/sismo-la/>** : pas de backend, pas d’étape de
build, rien à payer.

**L’instantané publié ne porte aucune coordonnée.** La page encadre les
événements catalogués que la station a reconnus et trace la magnitude qu’elle
a lue contre la magnitude publiée par l’USGS ; rien de tout ça n’a besoin de
savoir où est la boîte. Ça a aussi retiré une malhonnêteté — l’ancien marqueur
d’épicentre rouge n’atterrissait quelque part que parce qu’il empruntait
l’azimut à l’événement qu’il était censé estimer. Mettez
`publish.include_location: true` pour remettre la station sur la carte.

Rien ne vit seulement en mémoire : chaque secousse est ajoutée à
`event_log.jsonl` à côté des trois fichiers d’état des modèles, sur le système
de fichiers de l’hôte plutôt que du conteneur, donc le dossier survit aux
redémarrages, reboots et réinstallations.

## Organisation du dépôt

```
sismo-la/
├── app.yaml                   # manifeste App Lab (nom, ports, bricks)
├── python/                    # tourne sur le MPU Dragonwing (Debian)
│   ├── main.py                # point d’entrée : boucles + tableau de bord + publisher
│   ├── pipeline.py            # aides détection/corrélation + CLI sans interface
│   ├── usgs.py                # client FDSN USGS
│   ├── calibration.py         # modèle d’amplitude + modèle de distance (persistés)
│   ├── classifier.py          # régression logistique séisme-vs-bruit en ligne
│   ├── envelope.py            # enveloppe continue, un CSV par jour UTC
│   ├── retro.py               # recherche à l’instant d’arrivée qu’implique le catalogue
│   ├── expected.py            # ce qui aurait dû être ressenti, vs ce qui l’a été
│   ├── audit.py               # notation hors échantillon à partir du journal
│   └── dashboard/index.html   # tableau de bord opérateur
├── sketch/                    # tourne sur le MCU STM32U585 (Zephyr)
├── deploy/                    # démarrage autonome sans root : sidecar watchdog
├── docs/                      # architecture, calibration, matériel, récit
└── web-remote/                # publié sur GitHub Pages
```

## État

- [x] Nœud autonome sur du vrai matériel : détecter → recouper → apprendre → publier.
- [x] Survive à une coupure de courant sans humain (4 min 24 s jusqu’à un tableau de bord qui sert).
- [x] Seuil de détection mesuré, et le taux de détection attendu avec.
- [x] Loi d’atténuation réajustée sur 12 324 amplitudes ShakeMap réelles.
- [x] Enveloppe continue enregistrée, et cherchée rétrospectivement à l’instant
      d’arrivée qu’implique le catalogue — un facteur 7 à 8 en amplitude, tenu
      strictement à part de ce sur quoi la station déclenche toute seule.
- [x] **Premier vrai séisme confirmé** (M3,2, 2 septembre). Trouvé dans
      l’enveloppe stockée à l’instant d’arrivée qu’implique le catalogue — la
      station n’a rien remarqué sur le moment, et le déclencheur aveugle avait
      besoin de trois fois l’amplitude.
- [ ] **Premier séisme que la station attrape toute seule — toujours aucun**,
      et la calibration d’amplitude toujours à 0 sur 8, puisque les
      confirmations n’ont pas le droit de l’alimenter. Tout le reste attend
      ça.
- [x] Auto-audit contre le catalogue : chaque événement catalogué classé hors
      de portée, marginal, vu, ou **aurait dû être vu et ne l’a pas été**.
      Actuellement 0 dans la dernière catégorie, donc le silence est le
      catalogue et pas une panne.
- [ ] Courbe de calibration à partir de vrais enregistrements, avec résidus
      tenus de côté.
- [ ] Vidéo du concours : mode replay plus un tap en direct.

Candidature au concours
[Invent the Future with Arduino UNO Q and App Lab](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab)
— catégorie **Best Social Impact**, clôture des soumissions le
**13 septembre 2026**. Récit dans
[`docs/hackster-story.md`](docs/hackster-story.md).

## Licence

MIT — voir [`LICENSE`](LICENSE).
