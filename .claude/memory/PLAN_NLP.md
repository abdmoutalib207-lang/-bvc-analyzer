# Plan de reconstruction du pilier NLP

> Arrêté le 03/09/2026 avec Abd Moutalib. Fusion de deux propositions —
> l'ossature vient de Grok, les corrections viennent de mesures faites sur le
> corpus réel. **Suivre cet ordre.** Chaque étape existe parce que l'étape
> suivante est fausse sans elle.

## Pourquoi ce chantier

Le pilier NLP pèse **28 % du score composite** et il est aujourd'hui creux :
le calcul publié date du 4 juin 2026, deux phases sur quatorze étaient mortes
depuis des mois, et une vingtaine de titres affichent zéro alors qu'ils ont un
corpus. Le terminal présente donc une note dont plus d'un quart repose sur
presque rien.

## Les trois mesures qui fondent le plan

Faites le 02 et 03/09/2026 sur les 919 372 messages (2020-09 → 2026-07).

**1. Le fil vaut douze fois la mention.** Compter les messages qui *contiennent*
le code d'un titre donne 48 832 messages exploitables. Suivre la conversation
— tant que l'écart reste sous 10 minutes et qu'aucun autre titre n'est cité —
en donne **591 430**, soit 64 % du corpus au lieu de 5 %.

    titre    mentions/jour    fil/jour
    ADI            4      →      49
    RDS            4      →      58
    titres avec ≥10 msg/jour :  0  →  15

**2. Cinq auteurs écrivent plus du tiers du corpus.**

    top   5 auteurs → 35,6 %
    top  15 auteurs → 50,3 %
    top  50 auteurs → 71,2 %

Sans plafond par auteur, le modèle apprendrait le style de cinq personnes.

**3. Le corpus est à 98,2 % en écriture latine** — français, darija
translittérée, boursier local. L'arabe ne pèse que 1,8 %. Un modèle anglophone
(FinBERT) n'y verrait presque rien.

## Les étapes

### 0 — Découper le corpus en fils
Unité de travail : le fil, pas le message. 30 600 fils, 11 messages en médiane.
Sans cette étape on annote des messages hors contexte, et le modèle apprend à
juger « ghadi tzid » sans savoir de quoi ça parle.
⚠️ Seuil de 10 min **arbitraire** — 30 min donne ×15,1. À valider à l'œil.

### 1 — Instantané figé et rejouable
Un fichier versionné, pseudonymisé, avec `msg_id`, `ts`, `author_id`, `text`,
`lang`, `tickers[]`, `fil_id`.
⚠️ **Pas de colonnes réactions / réponses** : un export WhatsApp n'en contient
aucune, et les citations pèsent 0,12 %. Le facteur « engagement » des deux
propositions initiales porte sur du vide — ne pas le prévoir.

### 2 — 20 fils de contrôle
Abd Moutalib les relit. Objectif unique : le découpage tient-il ? Si le seuil
coupe au mauvais endroit, le savoir avant d'en produire 500.

### 3 — 500 fils annotés (le vrai premier livrable)
Schéma : `tickers` · `regime` (accumulation / distribution / fomo / confiance /
attente / peur / panique / capitulation / hors-sujet) · `polarite` (−2…+2) ·
`intensite` (1-5) · `ironie` · `horizon` · `actionnable`.

- **Plafond par auteur** — sinon on annote cinq personnes.
- **Composition** : 200 au hasard · 150 sur les titres les plus discutés ·
  100 des comptes smart money · 50 cas volontairement durs.
- **Double annotation sur 100 fils** : Abd Moutalib, puis Claude. On mesure
  l'écart. Un désaccord signale une consigne mauvaise, pas un annotateur
  mauvais. (Le κ de Cohen suppose deux annotateurs ; il n'y en a qu'un ici,
  d'où cette adaptation.)

### 4 — Lexique BVC : le plancher à battre
300 termes locaux — ramassage, distribution, coincé, carnet vide, ATO,
réservée, vendeur caché, t9leb… Mesuré sur les 500 fils annotés.
**Règle : tout modèle qui ne bat pas le lexique n'entre pas dans le terminal.**

### 5 — Premier modèle
`atlasia/XLM-RoBERTa-Morocco` ou DarijaBERT, affiné sur les fils annotés.
⚠️ **Découpage temporel, jamais aléatoire** : entraînement ≤ 2024, test
2025-2026. Un tirage au hasard mélange le futur au passé et produit un score
flatteur et faux.
Pas de pré-entraînement continu (DAPT) avant que le jeu annoté existe.

### 6 — Couplage au marché
Sentiment × cours × volume, divergences, mesure à J+1, J+3, J+5, J+20.
C'est ici seulement que le NLP devient un facteur quantitatif.

## Ce qu'on ne fait pas

- Affiner un très gros modèle.
- Réétiqueter le corpus avec un LLM et appeler ça la vérité.
- **Toucher aux 28 % du score avant d'avoir publié un F1 sur le jeu annoté**
  (règle R8).

## ⚠️ La contrainte qui domine tout

**Le corpus est gelé au 02/07/2026.** L'accès au groupe est perdu. Tester sur
2025-2026 consomme donc les dernières données disponibles : une fois servies à
la validation, il ne reste rien de frais pour vérifier que le modèle tient.

Retrouver un accès régulier vaut plus que n'importe quelle étape ci-dessus.
Abd Moutalib s'en charge (déclaré le 03/09).
