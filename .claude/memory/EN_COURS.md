# En cours — à lire au démarrage de chaque session

> Mis à jour le **28/08/2026, 21h00 Casablanca**.
> Ce fichier est court par construction. Ce qui est terminé en sort et va dans
> le journal du CLAUDE.md ; ce qui est appris va dans LEARNINGS.md.

---

## 🔔 ATTENDU DE ABD MOUTALIB

- [ ] **Corpus WhatsApp à jour — promis pour le 29/08/2026.**
  Il a annoncé le 28/08 au soir qu'il le partagerait « demain » pour que
  l'analyse NLP reste à jour. **Le lui rappeler s'il ne l'a pas mentionné en
  début de session.**
  - Destination : `whatsapp_analysis/` — les sorties actuelles datent du
    **04/08/2026**, soit 24 jours de retard.
  - Dès réception, passer la main à l'agent `analyste-nlp`.
  - ⚠️ **Pseudonymiser les participants avant tout traitement publié** (CNDP).
    Aucun nom, numéro ou identifiant direct ne doit atteindre un fichier du
    dépôt.
  - Il a aussi évoqué de produire des fenêtres glissantes **3 mois et 6 mois**
    en plus de l'historique complet.

---

## ⚠️ INCERTAIN — à vérifier lundi 31/08 au matin

- [ ] **Le réveil externe fonctionne-t-il ?**
  Une routine « BVC — réveil des robots » a été créée le 28/08 (lundi→vendredi,
  9h45 · 12h45 · 15h45 · 18h45 Casablanca). Elle demande à sa session de
  déclencher `update_bvc.yml` et `fetch_news.yml` via les outils GitHub.
  - ⚠️ Un avertissement à la création signale que **les sessions déclenchées
    n'auront peut-être pas ces outils**. Si c'est le cas, la routine échouera et
    enverra une notification.
  - Le correctif prévu — une version autonome qui fait tourner le pipeline
    elle-même — n'a pas pu être créé : le service de routines s'est déconnecté.
  - **Premier déclenchement : lundi 31/08 à 8h45 UTC.** Vérifier le résultat.
  - Repli manuel si besoin : déclencher `update_bvc.yml` puis `fetch_news.yml`.

---

## 📋 FEUILLE DE ROUTE — 8 semaines vers un produit stable

L'ordre est délibéré. Ne pas le réordonner sans raison écrite.

1. **Filet de tests** (`ingenieur-tests`) — 2 à 3 jours.
   0 test aujourd'hui. Sans lui, aucun refactoring n'est raisonnable et aucune
   règle R1–R10 n'est vérifiable autrement qu'à la main.
2. **Réveiller le NLP** (`analyste-nlp`) — 1 semaine.
   28 % du score ; 29 titres sur 81 seulement ont un score non nul.
3. ~~**Mentions légales**~~ — ✅ fait le 28/08 (composant `MentionLegale`).
   ⚠️ Reste à faire relire par un juriste connaissant l'AMMC.
4. **Publier le backtest** (`quant-backtest`) — 3 à 4 jours.
   `phase11_backtest.py` existe, ses résultats ne sont nulle part dans l'UI.
5. **Découper `run()`** — 1 semaine, par tranches. **Après l'étape 1, jamais
   avant.** 768 lignes, 126 variables locales, 8 niveaux d'imbrication.
   Première tranche visée : la fusion des sources.
6. **Accessibilité et mobile** — 3 jours. 1 seul attribut `aria` dans tout le
   frontend (ajouté avec la mention légale).

## 🧑‍💼 Recrutements humains prioritaires

Les agents couvrent l'exécution ; ces trois rôles couvrent ce qu'un agent ne
peut pas trancher :
- **Juriste AMMC / CNDP** — droit de publier, puis de monétiser.
- **Data scientist NLP** — valider la méthode, pas seulement la brancher.
- **Quant** — valider empiriquement la pondération 25 / 47 / 28, jamais testée.
