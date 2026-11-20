#!/usr/bin/env python3
"""Pas d'écriture sans séance — lot 3.3 de la feuille de route (20/11/2026).

POURQUOI CE FICHIER
───────────────────
Critère du lot : « zéro commit de données hors séance sur 30 jours » (audit
Manus MJ-10). Mesuré sur `origin/main` du 21/10 au 20/11/2026 : **35 commits
`data:`** un week-end ou un jour férié — 26 d'`update_bvc` (13 le 18/11, fête
de l'Indépendance ; 11 le 06/11, Marche Verte ; 1 le samedi 07/11 ; 1 le
dimanche 01/11), 7 du pipeline v9 et 2 de `fetch_historical_data`.

Ce qu'ils contenaient, mesuré commit par commit (contenu JSON comparé au
parent, pas le nombre de lignes du diff) :

    data.json                 aucun cours, variation, volume ni date de séance
                              modifié — 0 titre sur 26 commits. Seuls changent
                              `updated`, `generated_at`, les âges en jours, des
                              seuils ±10 % qui apparaissent et disparaissent
                              d'un passage à l'autre, et deux effets de code
                              fusionné ce jour-là (retrait v5.3, cap de NRJ)
    briefing*.json            `ecrit_a` et la liste des actualités
    financial_data.json (v9)  `timestamp` SEUL, sur les 7
    historical_data.json      `_updated` et `h90` — une fenêtre CALENDAIRE qui
                              glisse d'un jour, sans aucune bougie nouvelle
    chandelles                aucune, sur les 35
    news.json, marchés mondiaux, change MAD/TND : du contenu réel

Chacun de ces commits reconstruisait GitHub Pages — la ressource rare du
projet — pour republier la séance de la veille avec une nouvelle heure.

CE QUI TRANCHE
──────────────
⚠️ Aucun calendrier de jours fériés. La séance se déduit des données, comme
pour les séances fantômes (14/08) : la séance que porte un `data.json` est la
date `_meta.prix_asof` majoritaire (`porte_rattrapage.seance_portee`), et le
moteur la ramène déjà à la séance réelle quand une source rediffuse la veille
datée du jour (`update_data._recaler_seance_fantome`).

Les fichiers de cotation (data.json, chandelles, briefings, historiques…)
partent seulement si :

  1. le fichier généré porte la séance DU JOUR — et n'est pas une rediffusion
     de la publication précédente (second filet, si le recalage du moteur
     n'a pas joué) ; ou
  2. il porte une séance plus récente que celle publiée — un rattrapage,
     par exemple la clôture d'hier ramenée par un run de 00h55 ; ou
  3. les cours de la séance qu'il porte diffèrent de ceux publiés — une
     clôture qui remplace un cours de mi-séance, une correction.

Hors de ces trois cas, il n'y a rien de neuf à dire sur la Bourse : seuls les
fichiers de `FICHIERS_HORS_SEANCE` — actualités, marchés mondiaux, change —
peuvent partir, et ils partent sous un message `news:`, pas `data:`.

⚠️ CE QUE CELA DIFFÈRE, ET C'EST VOULU. Un changement de code fusionné un
jour sans séance (champ retiré, capitalisation recalculée) n'atteint
`data.json` qu'au premier passage de la séance suivante. Pour publier quand
même, lancer `update_bvc` à la main avec l'entrée `forcer_ecriture`.

    python pipeline/garde_hors_seance.py cotation   # update_bvc : généré vs HEAD
    python pipeline/garde_hors_seance.py seance     # v9, historique : HEAD seul
    python pipeline/garde_hors_seance.py cotation --date 2026-11-18
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from bvc_config import heure_maroc  # noqa: E402
from pipeline.porte_rattrapage import seance_portee  # noqa: E402
from pipeline.seance import MIN_TITRES, SEUIL  # noqa: E402

# Les seuls fichiers qu'`update_bvc` peut commiter un jour sans séance. Ils ne
# décrivent pas la Bourse de Casablanca : les actualités paraissent le
# week-end, les marchés étrangers cotent nos jours fériés, la BCT publie ses
# taux, l'AMMC ses dépôts. Tout fichier absent de cette liste est réputé de
# cotation — un nouveau fichier est donc bloqué hors séance par défaut.
# ⚠️ La liste est recopiée dans `update_bvc.yml` ; un test vérifie l'égalité.
FICHIERS_HORS_SEANCE = (
    "news.json",
    "marches_mondiaux.json",
    "datasets/change_mad_tnd.json",
    "pipeline/depots_ammc.json",
)

# Ce qui fait une cotation. Les seuils ±10 %, la source retenue ou les
# moyennes ne sont pas des cours : mesuré le 18/11, les seuils de 54 titres
# apparaissaient et disparaissaient d'un passage à l'autre, sans séance.
CHAMPS_COTATION = ("price", "chg", "vol", "echange_dh", "open", "close")


def _asof(t: dict):
    return (t.get("_meta") or {}).get("prix_asof")


def rediffusion(genere: dict, publie: dict, aujourd_hui: str) -> tuple[int, int]:
    """(cours identiques, titres comparés) entre les lignes datées du jour du
    fichier généré et leur ligne publiée d'une séance antérieure.

    Même test que `seance.purger_seance_fantome` : une séance réelle ne
    reproduit jamais toutes les clôtures au centime (6/44 le 13/08), une
    rediffusion les reproduit toutes (71/71 le 14/08).
    """
    pub = {t.get("symbol"): t for t in publie.get("tickers") or []}
    ident = total = 0
    for t in genere.get("tickers") or []:
        p = pub.get(t.get("symbol"))
        if _asof(t) != aujourd_hui or not p or not (_asof(p) or "") < aujourd_hui:
            continue
        a, b = t.get("price"), p.get("price")
        if not a or not b:
            continue
        total += 1
        ident += round(float(a), 2) == round(float(b), 2)
    return ident, total


def cotation_modifiee(genere: dict, publie: dict) -> list[str]:
    """Les titres (et « MASI ») dont la cotation diffère de la publication."""
    pub = {t.get("symbol"): t for t in publie.get("tickers") or []}
    diff = []
    for t in genere.get("tickers") or []:
        p = pub.get(t.get("symbol"))
        if p is None:
            if t.get("price"):
                diff.append(t.get("symbol"))
            continue
        if _asof(t) != _asof(p) or any(t.get(c) != p.get(c) for c in CHAMPS_COTATION):
            diff.append(t.get("symbol"))
    mg, mp = genere.get("masi") or {}, publie.get("masi") or {}
    if any(mg.get(c) != mp.get(c) for c in ("value", "change_pct", "asof")):
        diff.append("MASI")
    return diff


def decider(genere: dict | None, publie: dict | None, aujourd_hui: str) -> tuple[bool, str]:
    """(les fichiers de cotation peuvent-ils partir, pourquoi). Pure."""
    if not publie:
        return True, "aucune publication antérieure lisible — écriture autorisée"
    if not genere:
        return True, "fichier généré illisible — décision laissée aux contrôles bloquants"
    s_gen, s_pub = seance_portee(genere), seance_portee(publie)
    if s_gen is None:
        return True, "le fichier généré ne porte aucune séance — décision laissée aux contrôles"
    if s_gen > aujourd_hui:
        return True, f"séance {s_gen} postérieure au {aujourd_hui} — anomalie laissée aux contrôles"
    if s_gen == aujourd_hui:
        ident, total = rediffusion(genere, publie, aujourd_hui)
        if total >= MIN_TITRES and ident / total >= SEUIL:
            return False, (f"séance du {aujourd_hui} annoncée, mais {ident}/{total} cours "
                           f"identiques à la publication du {s_pub} : rediffusion d'un "
                           "jour sans cotation")
        return True, f"séance du jour ({aujourd_hui})"
    if s_pub is None or s_gen > s_pub:
        return True, f"séance {s_gen} pas encore publiée (publication : {s_pub}) — rattrapage"
    diff = cotation_modifiee(genere, publie)
    if diff:
        return True, (f"séance {s_gen} : cotation modifiée sur {len(diff)} ligne(s) "
                      f"({', '.join(map(str, diff[:8]))}{'…' if len(diff) > 8 else ''})")
    return False, (f"pas de séance le {aujourd_hui} : le fichier porte le {s_gen}, déjà "
                   "publiée à l'identique — seuls des champs hors cotation changent")


def publie(racine: Path, ref: str = "HEAD") -> tuple[dict | None, str]:
    """Le `data.json` de `ref`, ou (None, raison). Lu par git : le fichier du
    répertoire de travail est, lui, celui que le run vient de générer."""
    r = subprocess.run(["git", "show", f"{ref}:data.json"], cwd=racine,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, f"git show {ref}:data.json a échoué : {r.stderr.strip()}"
    try:
        return json.loads(r.stdout), ""
    except ValueError as e:
        return None, f"{ref}:data.json illisible : {e}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=("cotation", "seance"))
    ap.add_argument("--date", help="AAAA-MM-JJ (défaut : aujourd'hui, heure du Maroc)")
    ap.add_argument("--ref", default="HEAD", help="révision publiée (défaut : HEAD)")
    a = ap.parse_args(argv)
    racine = Path.cwd()
    jour = a.date or heure_maroc().date().isoformat()
    pub, raison_pub = publie(racine, a.ref)
    if raison_pub:
        print(f"⚠️ {raison_pub}")

    if a.mode == "seance":
        s = seance_portee(pub) if pub else None
        ok = pub is None or s == jour
        print(f"seance={'true' if ok else 'false'}")
        print(f"séance publiée : {s} ; aujourd'hui : {jour}"
              + ("" if ok else " — pas de séance aujourd'hui, rien à publier (lot 3.3)"))
        return 0

    genere = json.loads((racine / "data.json").read_text(encoding="utf-8"))
    ok, pourquoi = decider(genere, pub, jour)
    print(f"cotation={'true' if ok else 'false'}")
    print(pourquoi)
    return 0


if __name__ == "__main__":
    sys.exit(main())
