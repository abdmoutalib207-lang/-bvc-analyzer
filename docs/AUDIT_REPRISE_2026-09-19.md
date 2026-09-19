# Reprise du 19 septembre 2026

## Verdict

Le projet avance : les historiques documentés, les contrôles d'identité et la
politique commune d'écriture constituent des améliorations réelles. La fiabilité
quotidienne n'est toutefois pas encore acquise. Une CI verte ne prouve ni que le
moteur a travaillé, ni que le site a publié la dernière séance.

## Incident du 18 septembre

Base examinée : `3a92a59a8cd1cc44b12d20058a5704af48d33542`, après fusion de #63.
`data.json` est daté du 19/09 à 16:03:50 Casablanca et porte déjà les cours du
18/09. Les chandelles restent au 16/09 : aucune du 18 n'était enregistrée.
La séance du 17 a été annulée ; elle ne doit pas être recréée.

La PR #61 a déjà corrigé le repli temporel lors d'une annulation et synchronise
le cache avant les tests de publication. La PR #63 autorise un rattrapage après
la date de séance, mais fabrique encore les extrêmes depuis ouverture/clôture.
Exemple ADI : le bas réel est 376, pas 377. Le problème n'est donc pas seulement
un retard de planification : plusieurs étages doivent rester cohérents.

## Correctif complémentaire

- Bulletin PDF primaire archivé : `pipeline/bulletins/CDG_indices_2026-09-18.pdf`.
  SHA256 : `911d171e68094733a962d6227d4dbe00328a21b461075331f366b806e9d9e915`.
  Les 81 lignes correspondent au JSON de #62 ; 66 portent des échanges.
- Reprise sélective de l'importeur de #62, sans fusionner ses workflows ni son
  ancien tableau de bord. Validation des dates, identités, OHLCV et suspensions.
- Ajout de 66 chandelles exactes. Toutes les séances antérieures sont inchangées.
  MDP et SLM commencent seulement au 18 : aucun passé n'est inventé.
- Codes officiels traduits avant utilisation : SID → SNA interne (Sonasid,
  1 800 DH), SNA → STK interne (Stokvis, 63,26 DH).
- Moteur : chandelles complètes CDG/BMCE seulement, jamais de haut/bas déduits
  d'un cours seul. Mise en mémoire avant les calculs ; cache avancé dans le même
  run. Les divergences historiques du cache sont préservées et restent à arbitrer.
- Surveillance : séance attendue obtenue auprès de CDG et non des chandelles du
  dépôt. Une source inaccessible produit une erreur explicite, pas un faux vert.
- Rattrapage nocturne : la présence de prix récents ne suffit plus si les
  graphiques manquent. Historique MASI inclus dans le commit ; journal des
  annulations conservé à chaque ajout.

Les quantités du bulletin sont retenues pour ce lot. Un relevé API antérieur
différait du PDF sur 11 quantités (pas sur les 66 OHLC) : l'accord sur les cours
ne doit pas être présenté comme une validation de tous les champs.

## État de la feuille de route

Vérification locale du candidat : **914 tests réussis, 2 ignorés**. Le moteur
a été rejoué avec les réponses CDG/IDB/MASI réellement collectées et le repli
historique local (Médias24 non sollicité dans ce replay). Les 66 prix et
chandelles concordent avec le bulletin. Une copie repartant du 16/09 éprouve
l'ajout automatique et le dry-run sans écriture ; ses 80 prix et indicateurs
contrôlés concordent avec le candidat préparé depuis le PDF. La CI GitHub
doit encore juger la collecte réseau complète avant fusion.

| Chantier | État vérifié / suite |
|---|---|
| MSA, correction des 22 séances | Déjà intégrée ; ne pas refaire ce lot |
| Sothema et protections de séries corrigées | Correctifs antérieurs conservés ; pas de recalcul complet généralisé |
| Sonasid / Stokvis | Historiques complets importés dans #59 ; traduction commune protégée |
| T2S | Série courte liée à sa cotation récente ; ne pas fabriquer trois ans de données |
| CMT | Reprise réelle du 16/09 conservée ; cours 2 681 le 18, indicateurs post-reprise insuffisants signalés |
| Fondamentaux | 31 émetteurs documentés, 29 PB calculables ; #60 encore distincte et non réceptionnée |
| Quotidien automatique | Correctif présent dans ce lot ; stabilité sur 30 séances à démontrer |
| Historiques longs | 78 séries stockées, dont 24 sous 250 séances ; imports encore incomplets |
| NLP / scores explicables / backtest | Travaux distincts, pas certifiés achevés par cet incident |

## Anomalies restantes, ordre de traitement

1. Assainir le cache **titre par titre** avec preuves : 655 chandelles OHLC
   incohérentes sur 11 clés (CASH 34, CFGB 31, CMGP 55, MSA 54, RDS 57,
   RIS 60, SGTM 47, SMI 83, SRM 80, TGC 92, VCNE 62). Ne pas annuler les
   corrections réceptionnées de CFGB/CMGP ni changer l'échelle de Sothema.
   Le plus-bas SGTM 508,1 est conservé ; la divergence avec 461,95 brut reste
   à arbitrer explicitement.
2. Traiter les **61 séries portant encore le 30/07/2026**, férié fixe, par un
   lot séparé avec comparaison des indicateurs avant/après. L'ancien suivi
   annonçait 67 : les imports intervenus depuis en ont déjà nettoyé une partie.
3. Compléter les historiques sources, dont les écarts/parties manquantes SMI,
   en distinguant absence de transaction et données inconnues. Les exports ADI,
   SMI et T2S fournis ne justifient jamais de réécrire toutes les autres valeurs.
4. Vérifier les prochaines clôtures réellement servies, puis consolider le
   moteur. `run()` reste volumineux ; extraire les règles testables progressivement,
   sans multiplier les workflows concurrents de publication.

L'envoi du bulletin par courriel nécessite toujours sa configuration dédiée.
Les anciens sujets de confidentialité et de droits sur les données ne sont pas
résolus par cette correction technique.
