#!/usr/bin/env python3
"""Ce que le terminal a publié, jour par jour, pour qu'on puisse le mesurer plus tard.

⚠️ POURQUOI CE FICHIER EXISTE — LE 25/09/2026, UNE DÉCISION A REPOSÉ SUR 13 JOURS
──────────────────────────────────────────────────────────────────────────────────
Le backtest lit les scores dans l'historique git de `data.json` : 1 920 commits,
87 jours reconstitués. Ça marche, et c'est de l'**archéologie**. Une fouille ne
retrouve que ce qui avait été enterré : `score_fond` et `score_nlp` n'apparaissent
dans le flux que depuis le **12/09/2026**.

Conséquence concrète, et elle a été payée : quand il a fallu établir si retirer
le pilier NLP dégradait le score, la mesure n'a pu porter que sur **13 jours et
194 observations** — là où 87 jours étaient disponibles pour `v53` seul. La
décision a été prise sur un seul régime de marché parce que la donnée qui
l'aurait éclairée n'avait pas été écrite en son temps.

**Ce module écrit aujourd'hui ce qu'une mesure future réclamera.** Il ne répond
à aucune question actuelle — c'est précisément sa raison d'être.

⚠️ CE QU'IL APPARIE, ET POURQUOI L'APPARIEMENT SE FAIT À L'ÉCRITURE
Le relevé joint, dans le même enregistrement : les notes par pilier, les poids
RÉELLEMENT appliqués ce jour-là, le signal, la confiance, le prix — **et l'état
du marché de la séance**. Les rapprocher après coup obligerait à supposer que
les deux fichiers parlent de la même séance ; les écrire ensemble l'établit.

C'est ce qui rendra mesurable, vers fin octobre, la question laissée ouverte :
la largeur de marché a-t-elle une valeur prédictive ? Elle ne compte qu'**une
séance d'historique au 25/09** et ne peut donc pas être évaluée aujourd'hui.

⚠️ CE QUE CE FICHIER N'EST PAS
Ce n'est pas une source. `data.json` reste le flux publié et les chandelles
restent l'autorité sur les cours. C'est un **journal**, en écriture seule et en
ajout : on n'y corrige pas le passé. Si un score publié était faux, il reste au
journal tel qu'il a été publié — sinon le backtest mesurerait un terminal qui
n'a jamais existé.

⚠️ FORME : COLONNES DÉCLARÉES, LIGNES EN TABLEAUX
Un dictionnaire par titre et par jour répéterait dix noms de champs 80 fois par
séance, soit environ 200 000 clés par an. Les colonnes sont donc déclarées une
fois dans `_colonnes`, et chaque titre est une liste de valeurs dans cet ordre.
Le fichier reste lisible et pèse environ trois fois moins.
"""

from __future__ import annotations

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CHEMIN = RACINE / "pipeline" / "score_history.json"

# ⚠️ L'ORDRE EST LE CONTRAT. Les lignes sont des tableaux : insérer une colonne
# ailleurs qu'à la fin décalerait la lecture de tout l'historique déjà écrit.
# Ajouter une colonne se fait EN FIN DE LISTE, et les anciennes lignes, plus
# courtes, se relisent sans erreur (cf. `lire()`).
COLONNES = [
    "symbol",      # le ticker, tel que le projet le nomme (pas celui de l'opérateur)
    "v53",         # la note publiée, bonus compris
    "score_fond",  # les trois piliers, pour pouvoir re-pondérer après coup
    "score_tech",
    "score_nlp",
    "poids_f",     # ⚠️ les poids RÉELLEMENT appliqués, pas ceux de référence :
    "poids_t",     #    le WeightEngine module par titre, et sans eux on ne
    "poids_n",     #    saurait pas reconstituer la note
    "sig",         # le signal affiché — c'est lui que le lecteur a vu
    "conf",        # la confiance 0-5 : en dessous de 2, le produit ne conclut pas
    "prix",        # le cours retenu ce jour-là
    "prix_asof",   # ⚠️ la séance du cours, qui n'est pas toujours celle du run
]

_INDEX = {c: i for i, c in enumerate(COLONNES)}


def _nombre(v, decimales=2):
    """Un nombre, ou None. `None` = « le flux ne l'a pas donné »."""
    if v is None or isinstance(v, bool):
        return None
    try:
        return round(float(v), decimales)
    except (TypeError, ValueError):
        return None


def _entier(v):
    n = _nombre(v, 0)
    return None if n is None else int(n)


def ligne_ticker(t: dict) -> list | None:
    """Un titre du flux → une ligne du journal. Fonction pure.

    ⚠️ Rend `None` si le titre n'a ni symbole ni note : un enregistrement vide
    gonflerait le journal sans rien apprendre. En revanche un titre dont la
    note existe mais dont la confiance est basse EST enregistré — c'est même
    le cas le plus intéressant, puisqu'il permettra plus tard de vérifier que
    le produit a eu raison de ne pas conclure.
    """
    if not isinstance(t, dict):
        return None
    sym = t.get("symbol")
    v53 = _nombre(t.get("v53"))
    if not sym or v53 is None:
        return None
    p = t.get("poids") or {}
    m = t.get("_meta") or {}
    return [
        sym, v53,
        _nombre(t.get("score_fond")), _nombre(t.get("score_tech")),
        _nombre(t.get("score_nlp")),
        _entier(p.get("f")), _entier(p.get("t")), _entier(p.get("n")),
        t.get("sig"), _entier(m.get("confidence")),
        _nombre(t.get("price")), m.get("prix_asof"),
    ]


def lire() -> dict:
    """Le journal, ou un journal vide. Ne lève jamais.

    ⚠️ Un journal illisible ne doit pas faire échouer un run de production :
    le relevé est une commodité pour plus tard, pas une dépendance du bulletin.
    """
    try:
        d = json.loads(CHEMIN.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get("seances"), dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def valeur(ligne: list, colonne: str):
    """Lit une colonne d'une ligne, en tolérant les lignes anciennes.

    ⚠️ Une ligne écrite avant l'ajout d'une colonne est plus COURTE. La lire
    par index sans garde lèverait `IndexError` sur tout l'historique ancien —
    c'est le piège exact d'un format positionnel, et il se paye des mois plus
    tard, quand personne ne se souvient du changement.
    """
    i = _INDEX.get(colonne)
    if i is None or not isinstance(ligne, list) or i >= len(ligne):
        return None
    return ligne[i]


def enregistrer(seance: str, tickers: list, etat_marche: dict | None = None) -> dict:
    """Ajoute — ou remplace — le relevé d'une séance. Écrit le fichier.

    ⚠️ LE DERNIER RUN DE LA JOURNÉE L'EMPORTE, délibérément. Le run de 15h45
    fixe le cours définitif ; celui de 9h30 publiait un cours de milieu de
    séance. Conserver le premier ferait mesurer un terminal que personne n'a
    lu à la clôture. C'est la même règle que pour la bougie du jour.

    ⚠️ AUCUNE SÉANCE ANTÉRIEURE N'EST TOUCHÉE. Le journal est en ajout : si un
    score passé était faux, il reste au journal tel qu'il a été PUBLIÉ. Le
    corriger ferait mesurer un terminal qui n'a jamais existé.
    """
    if not seance or not isinstance(tickers, list):
        return lire()

    lignes = [l for l in (ligne_ticker(t) for t in tickers) if l]
    if not lignes:
        # ⚠️ Un run qui n'a rien produit n'efface pas ce qui était enregistré.
        return lire()

    j = lire()
    j.setdefault("_note", "Journal en AJOUT de ce que le terminal a PUBLIÉ. "
                          "Ni source ni autorité — voir score_history.py.")
    j["_colonnes"] = COLONNES
    j.setdefault("seances", {})

    releve = {"tickers": lignes}
    if etat_marche:
        # ⚠️ Apparié ICI, pas après coup : rapprocher deux fichiers plus tard
        # obligerait à SUPPOSER qu'ils parlent de la même séance.
        releve["marche"] = {
            k: etat_marche.get(k) for k in
            ("variation_pct", "ytd_pct", "hausses", "baisses", "inchanges",
             "valeurs_traitees", "volume_mad")
            if etat_marche.get(k) is not None
        }
    j["seances"][seance] = releve

    CHEMIN.write_text(
        json.dumps(j, ensure_ascii=False, separators=(",", ":"), sort_keys=False),
        encoding="utf-8")
    return j


def seances() -> list[str]:
    """Les séances enregistrées, dans l'ordre."""
    return sorted(lire().get("seances") or {})
