# Incident de publication — précision des poids, 16 octobre 2026

Intervention exceptionnelle autorisée par Noure pour cette panne uniquement.
Elle ne constitue pas une autorisation permanente d'écriture sur le principal.

Les passages de 09h55, 10h55, 11h55 et 12h55 collectaient les cours mais
échouaient avant le commit : `tests/test_audit_chaine.py` recomposait la note
avec des pourcentages entiers, alors que `compute_v53` utilisait les fractions
à quatre décimales de `get_weights`.

Le correctif conserve deux décimales dans les pourcentages exportés par
`compute_v53` : 71,43 / 28,57 au lieu de 71 / 29. Il ne modifie ni la formule,
ni `get_weights`, ni les seuils de signal, ni les données fondamentales. La
tolérance de l'audit et les contrôles bloquants restent inchangés.

Cas de régression repris des journaux du passage de 12h55 : MUT 3,41,
CAR 3,30 et SMI 6,84. Onze tests couvrent ces trois cas et huit contextes,
en contrôlant simultanément la précision exportée et l'invariance de la note.
Comparaison indépendante avant/après sur les 80 fiches et quatre contextes
(320 appels) : aucune différence hors du champ `poids`, notamment sur les notes,
signaux et bonus. L'audit de chaîne sur le fichier régénéré passe sans changer
sa tolérance de 0,02.

La livraison doit être validée par la suite complète puis une collecte réelle.
Le workflow de collecte effectue explicitement son checkout sur `main` : une
relance d'un passage échoué doit donc lire le correctif après sa fusion.
