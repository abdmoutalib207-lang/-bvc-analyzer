# En cours — à lire au démarrage de chaque session

> Mis à jour le **30/08/2026, 02h15 Casablanca** (dimanche, marché fermé).
> Ce fichier est court par construction. Ce qui est terminé en sort et va dans
> le journal du CLAUDE.md ; ce qui est appris va dans LEARNINGS.md.

---

## 🔔 ATTENDU DE ABD MOUTALIB

- [ ] **Corpus WhatsApp à jour — ⚠️ ÉCHÉANCE DÉPASSÉE.**
  Annoncé le 28/08 au soir pour « demain », soit le samedi 29/08. Non reçu à ce
  jour. **Le lui rappeler dès le premier échange**, sans insister : c'est un
  week-end, et rien ne bloque tant que l'étape 2 n'a pas commencé.
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
  - **Premier déclenchement : LUNDI 31/08 à 8h45 UTC — c'est demain.**
    Vérifier le résultat plutôt que le supposer.
  - Repli manuel si besoin : déclencher `update_bvc.yml` puis `fetch_news.yml`.

---

## 📋 FEUILLE DE ROUTE — 8 semaines vers un produit stable

L'ordre est délibéré. Ne pas le réordonner sans raison écrite.

1. ~~**Filet de tests**~~ — ✅ **fait le 30/08**. 69 tests, 7 fichiers, moins
   d'une seconde, CI verte au premier run. Trois défauts trouvés en l'écrivant,
   dont un vrai bug (`est_ferie_fixe(None)` levait TypeError).
   ⚠️ Reste découvert et écrit dans `tests/README.md` : la fusion des sources,
   cœur de R3, **n'est pas testable tant qu'elle vit dans `run()`**. C'est
   l'argument de l'étape 5.
2. **Réveiller le NLP** (`analyste-nlp`) — 1 semaine. ← **prochaine étape**
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
