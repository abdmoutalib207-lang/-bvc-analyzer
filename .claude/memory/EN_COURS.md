# En cours — à lire au démarrage de chaque session

> Mis à jour le **31/08/2026, 11h40 Casablanca** (lundi, séance en cours).
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

## ⚠️ LE DÉCLENCHEMENT — le point faible du produit

- [x] **Le réveil externe se déclenche mais n'agit pas.** Constaté le 31/08 :
  la routine a bien démarré à 9h45, une session a été créée, et **rien ne s'est
  passé**. Cause : son message lui demandait d'utiliser les outils GitHub MCP,
  qu'elle n'a pas, tout en lui interdisant de commiter — elle n'avait donc ni
  moyen d'agir, ni droit d'agir autrement. Silence total, aucune notification.
  - **Correctif remis à Abd Moutalib** : un texte de remplacement à coller dans
    la routine (claude.ai → Routines → « BVC — réveil des robots »), qui ajoute
    une voie B autonome — faire tourner le pipeline soi-même et pousser, avec
    l'autorisation explicite de commiter dans ce cas.
  - ⚠️ **Non vérifié** : on ignore si la session déclenchée reçoit une copie du
    dépôt. Si non, la voie B échouera aussi — mais elle le DIRA cette fois.

- [x] **Redondance du soir posée le 31/08** (dans `update_bvc.yml`).
  Trois créneaux — 18h, 20h, 22h — au lieu d'un. L'observation qui la justifie :
  pour un bulletin J+1, l'échéance est **8h du matin, pas 18h**. Un run qui
  aboutit à 1h du matin publie à temps. Le cron de vendredi 17h UTC est parti
  samedi à 00h47 : il a tenu la promesse malgré 7h de retard.
  Coût nul — un run sans changement de fichier ne commite pas.

- ⚠️ **Le décalage de GitHub n'est plus de 30–50 min mais de 2 à 8 HEURES**, et
  certains crons ne partent pas du tout (lundi 31/08, 08h40 UTC : jamais parti).
  Ne plus se fier à l'heure inscrite dans un cron.

- ⚠️ **La promesse J+1 a été TENUE lundi matin** malgré tout : à 8h, le terminal
  affichait la clôture de vendredi, correctement datée. Ce qui a manqué est le
  rafraîchissement intraday, qui est un confort. Ne pas confondre les deux —
  c'est une erreur d'appréciation commise le 31/08.

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
5. **Découper `run()`** — en cours, par tranches.
   ✅ Tranche 1 faite le 31/08 : `fusionner_cotations()` extraite, 12 tests,
   validée sur 4 779 champs sans aucun écart. run() : 768 → 738 lignes.
   🔜 Tranche 2 : la boucle par ticker — c'est elle qui porte les 8 niveaux
   d'imbrication et la chaîne de repli complète (R1 + R3 en même temps).
6. **Accessibilité et mobile** — 3 jours. 1 seul attribut `aria` dans tout le
   frontend (ajouté avec la mention légale).

## 🧑‍💼 Recrutements humains prioritaires

Les agents couvrent l'exécution ; ces trois rôles couvrent ce qu'un agent ne
peut pas trancher :
- **Juriste AMMC / CNDP** — droit de publier, puis de monétiser.
- **Data scientist NLP** — valider la méthode, pas seulement la brancher.
- **Quant** — valider empiriquement la pondération 25 / 47 / 28, jamais testée.
