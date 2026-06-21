# Gabarit de soumission Hackster (pour rester dans les clous)

Synthese des regles a respecter, d'apres
[Content Guidelines](https://www.hackster.io/guidelines) et
[How to Create a High-Quality Project Tutorial](https://www.hackster.io/AlexWulff/how-to-create-a-high-quality-project-tutorial-e25feb).
On remplit cette page au fur et a mesure du projet.

## Conditions du concours (rappel)

- Doit utiliser l'**Arduino UNO Q** et **App Lab**.
- Catégorie visée : **Best Social Impact** (alt. Industrial IoT).
- Date limite de soumission : **30 août 2026**.
- Bonus appréciés : durabilité, expérience utilisateur, scalabilité, IA edge
  (Edge Impulse), intégration cloud (Arduino Cloud / AWS).

## Checklist qualité (Content Guidelines)

- [ ] **Nom** : phrase complète, descriptive de *ce que ça fait*, accrocheuse,
      sans URL. (Pas « Projet Arduino UNO Q » mais p.ex. « Un sismographe de
      quartier qui apprend des vrais séismes de Los Angeles ».)
- [ ] **Pitch** : une seule phrase, ne répète pas le nom, sans URL.
- [ ] **Cover image** : haute résolution, bonne lumière, **sans texte**, montre
      le résultat final (pas un plat de breadboard). Format 4:3.
- [ ] **Difficulté** : exacte.
- [ ] **Catégories** : max 3, décrivant ce que ça *accomplit* — éviter « Arduino »,
      mettre p.ex. « Monitoring », « Data collection », « Social impact ».
- [ ] **Things** : lister TOUS les composants réellement utilisés (UNO Q, IMU…),
      avec lien boutique quand possible. Logiciels/outils dans leurs sections.
- [ ] **Story** : structurée en étapes avec titres (pas un mur de texte), URLs
      cliquables, vidéos embarquées, **code en snippets** (pas en texte brut),
      images nettes.
- [ ] **Schematics** : section réservée aux schémas (Fritzing ou autre).
- [ ] **Code** : fichiers dans la section Code, bon langage sélectionné. Pas de
      placeholders pour gonfler la checklist.
- [ ] **Langue** : anglais correct, orthographe/ponctuation soignées.

## Structure recommandée de la Story (étapes)

1. **Le problème** — LA est sismique ; les vrais sismographes coûtent cher ; idée
   d'un nœud citoyen bas coût (cf. MyShake, Raspberry Shake).
2. **L'idée clé : l'étalonnage par USGS** — pourquoi un capteur pas cher devient
   utile quand on a une vérité-terrain gratuite.
3. **Matériel & branchements** — UNO Q + IMU (photo + schéma Fritzing).
4. **Le MCU temps réel** — STA/LTA expliqué simplement (snippet du `.ino`).
5. **Le Linux (Dragonwing)** — WiFi, flux USGS, corrélation (snippets Python).
6. **L'IA edge (Edge Impulse)** — séisme vs bruit, comment les données ont été
   collectées et le modèle entraîné.
7. **Le dashboard App Lab** — captures d'écran.
8. **Résultats & validation à LA** — courbe d'étalonnage, exemples de séismes
   réels correctement corrélés (preuves).
9. **Limites & suite** — honnêteté : détecteur local, pas télésismique.

## Conseils de rédaction & photos (tutoriel Wulff)

- Beaucoup de **photos** (gros plans, lumière abondante, angle constant).
- Prendre **plus de photos que nécessaire** pendant le build.
- Schémas via **Fritzing / CAD**, pas de croquis griffonné.
- Code **commenté**, valeurs nommées (pas de magic numbers), whitespace cohérent.
- Phrases **courtes et variées** ; mélange technique / accessible ; zéro faute.
- GIF possible en cover (mouvement = clics), mais résolution réduite.

## Médias à produire (à cocher)

- [ ] Photo de couverture (résultat final, soignée).
- [ ] Photo macro du montage UNO Q + IMU.
- [ ] Schéma Fritzing.
- [ ] GIF/vidéo d'une détection (tape sur la table -> déclenchement).
- [ ] Capture du dashboard.
- [ ] Capture d'une corrélation USGS réussie.
