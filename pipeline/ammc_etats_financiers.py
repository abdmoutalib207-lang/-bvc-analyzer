#!/usr/bin/env python3
"""Quand chaque société a publié ses derniers comptes — source AMMC.

⚠️ CE QUE CE MODULE RÉPOND, ET CE QU'IL NE FAIT PAS ENCORE
──────────────────────────────────────────────────────────
Les fondamentaux du terminal sont saisis à la main. Au 24/09/2026 ils ont entre
92 et 135 jours, et ils pèsent 47 à 52 % de la note. Le chantier est ouvert
depuis le 29/06 sans source fiable.

L'AMMC publie l'index des états financiers de tous les émetteurs cotés, et
l'expose en clair : liste paginée → fiche par rapport → PDF. Vérifié le
24/09/2026 depuis le conteneur, HTTP 200, sans authentification.

Ce module **relève l'index**. Il ne lit pas encore les PDF : extraire un
bénéfice par action de cent rapports aux mises en page hétérogènes est un
travail distinct, et le faire mal produirait des chiffres faux là où il n'y en
avait aucun.

Ce qu'il apporte déjà, et qui manquait entièrement :

    pour chaque société, LA DATE de son dernier état financier publié.

C'est ce qui permet de dire « nos fondamentaux d'ADI datent du 18/06 alors que
la société a publié ses comptes semestriels le 12/08 » — donc de savoir QUOI
rafraîchir, et de le prouver.

⚠️ L'IDENTITÉ NE SE DEVINE PAS
Le nom AMMC (« MAROC TELECOM ») et le nôtre (« Maroc Telecom ») se
rapprochent par normalisation, mais **un rapprochement approximatif est
refusé**. Une société non appariée est rendue telle quelle, à traiter à la
main — c'est la règle du projet : vérifier l'identité effectivement retournée
par le fournisseur, jamais la supposer.

⚠️ POURQUOI PAS DE FILTRE PAR ANNÉE
Le formulaire du site n'accepte pas ses propres paramètres en GET : passer
`field_annee_value_1=2026` rend la liste entière. La liste étant triée par
date décroissante, on lit les premières pages et on s'arrête — ce qui est plus
robuste qu'un paramètre que le site pourrait renommer.
"""

from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from bvc_config import COMPANY_NAMES  # noqa: E402

BASE = "https://www.ammc.ma"
LISTE = f"{BASE}/fr/liste-etats-financiers-emetteurs"

# La liste descend de 2026 à 2010 sur 426 pages. Trente suffisent largement
# pour couvrir deux exercices — environ quatre cents entrées — et bornent le
# nombre de requêtes envoyées à un site public.
PAGES_MAX = 30

# Une pause entre deux pages. Le site est celui du régulateur : on le lit, on
# ne le martèle pas.
PAUSE = 0.4


def _texte(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", html))


def normaliser(nom: str) -> str:
    """Un nom comparable : sans accents, sans ponctuation, sans forme sociale.

    ⚠️ Les formes sociales sont retirées parce qu'elles varient d'une source à
    l'autre sans changer l'identité — « TGCC S.A » et « TGCC SA » sont la même
    société. Ce qui reste doit correspondre ENTIÈREMENT, faute de quoi on
    refuse : « Crédit du Maroc » et « Crédit Eqdom » partagent un mot.
    """
    s = unicodedata.normalize("NFD", str(nom or ""))
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"\b(s\.?a\.?r?\.?l?\.?|sca|scs|snc|group|groupe)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def table_noms() -> dict[str, str]:
    """{nom normalisé: notre ticker}, construite depuis le référentiel."""
    return {normaliser(v): k for k, v in COMPANY_NAMES.items() if v}


def code_entre_parentheses(nom_ammc: str) -> str | None:
    """Le code que l'AMMC met entre parenthèses, s'il est un de NOS tickers.

    ⚠️ C'EST LA MEILLEURE PREUVE D'IDENTITÉ DISPONIBLE ICI, et elle n'est pas
    une ressemblance. L'AMMC écrit « Alliances Développement Immobilier (ADI) »,
    « Bank of Africa - Groupe BMCE (BOA) », « Compagnie Minière de Touissit
    (CMT) » : le code y est posé par l'émetteur lui-même.

    ⚠️ Deux garde-fous, et ils sont nécessaires :
      · le code doit figurer dans NOTRE univers — l'AMMC couvre aussi des
        émetteurs non cotés en actions (« Agence Nationale des Ports (ANP) »,
        « Crédit Agricole du Maroc (CAM) »), dont le code ne nous concerne pas ;
      · un code de trois ou quatre lettres pris au hasard dans un nom ne suffit
        pas : on n'accepte que ce qui est ENTRE PARENTHÈSES, à la fin.

    Ce que ce contrôle ne peut PAS faire : détecter un code que l'AMMC
    emploierait dans un autre sens que nous. Le projet en a déjà souffert —
    le `SNA` d'un opérateur désigne Stokvis, le nôtre Sonasid. D'où le
    recoupement de nom que fait `resoudre()` quand il le peut.
    """
    from bvc_config import TICKERS_ALL
    m = re.search(r"\(([A-Z0-9]{2,5})\)\s*$", str(nom_ammc or "").strip())
    if not m:
        return None
    code = m.group(1)
    return code if code in set(TICKERS_ALL) else None


def resoudre(nom_ammc: str, table: dict[str, str] | None = None) -> str | None:
    """Notre ticker, ou None si l'identité n'est pas établie.

    Deux voies, dans cet ordre :
      1. le code entre parenthèses, posé par l'émetteur — une identité DÉCLARÉE ;
      2. à défaut, le nom normalisé, en correspondance ENTIÈRE.

    ⚠️ La seconde voie exige l'égalité complète. Un rapprochement partiel
    marierait « Crédit du Maroc » à « Crédit Eqdom » — c'est exactement ainsi
    que Sonasid a hérité des cotations de Stokvis.
    """
    code = code_entre_parentheses(nom_ammc)
    if code:
        return code
    return (table if table is not None else table_noms()).get(normaliser(nom_ammc))


def _lire(url: str, get=None) -> str:
    if get is not None:
        return get(url)
    r = urllib.request.Request(
        url, headers={"User-Agent": "bvc-analyzer (contact: dépôt GitHub)"})
    with urllib.request.urlopen(r, timeout=30) as rep:
        return rep.read().decode("utf-8", "replace")


def parser_page(html: str) -> list[dict]:
    """Les entrées d'une page de la liste. Fonction pure, testable hors réseau.

    Une ligne porte : le nom de l'émetteur, l'année, le type de rapport, et le
    lien vers la fiche qui contient le PDF.
    """
    out = []
    for bloc in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        lien = re.search(r'href="(/fr/espace-emetteurs/etats-financiers/[^"]+)"',
                         bloc)
        if not lien:
            continue
        champs = [c.strip() for c in _texte(bloc).split("|") if c.strip()]
        annee = next((c for c in champs if re.fullmatch(r"20\d\d", c)), None)
        type_r = next((c for c in champs if "rapport" in c.lower()), None)
        nom = next((c for c in champs
                    if c != annee and c != type_r and len(c) > 2
                    and not re.fullmatch(r"20\d\d", c)), None)
        if not nom:
            continue
        out.append({"emetteur_ammc": nom, "annee": annee, "type": type_r,
                    "fiche": BASE + lien.group(1)})
    return out


def collecter(pages=PAGES_MAX, get=None, pause=PAUSE) -> list[dict]:
    """L'index des états financiers récents, page par page.

    S'arrête dès qu'une page ne rend rien — la liste est finie, ou le site a
    changé de forme, et dans les deux cas insister n'apporte rien.
    """
    vues, entrees = set(), []
    for p in range(pages):
        url = LISTE if p == 0 else f"{LISTE}?page={p}"
        try:
            lot = parser_page(_lire(url, get))
        except Exception:
            break
        if not lot:
            break
        for e in lot:
            cle = (e["emetteur_ammc"], e["annee"], e["type"])
            if cle not in vues:
                vues.add(cle)
                entrees.append(e)
        if pause and get is None:
            time.sleep(pause)
    return entrees


def par_societe(entrees: list[dict]) -> dict:
    """{ticker: dernière publication connue}, et ce qui n'a pas été apparié.

    ⚠️ Le second bloc compte autant que le premier : une société non appariée
    n'est pas absente de l'AMMC, elle est absente de NOTRE table de noms — et
    c'est une information sur nous, pas sur elle.
    """
    table = table_noms()
    connus, inconnus = {}, {}
    for e in entrees:
        tk = resoudre(e["emetteur_ammc"], table)
        if tk is None:
            inconnus[e["emetteur_ammc"]] = inconnus.get(e["emetteur_ammc"], 0) + 1
            continue
        precedent = connus.get(tk)
        # Plus récent = année supérieure, ou semestriel à année égale.
        rang = (int(e["annee"] or 0), 1 if "semestre" in (e["type"] or "").lower() else 0)
        if precedent is None or rang > precedent["_rang"]:
            connus[tk] = {**e, "_rang": rang}
    for v in connus.values():
        v.pop("_rang", None)
    return {"par_ticker": connus, "non_apparies": dict(sorted(inconnus.items()))}


def main() -> int:
    entrees = collecter()
    r = par_societe(entrees)
    couverts = set(r["par_ticker"])
    print(json.dumps({
        "entrees_relevees": len(entrees),
        "societes_appariees": len(couverts),
        "tickers_sans_etat_financier": sorted(set(COMPANY_NAMES) - couverts),
        "noms_ammc_non_apparies": r["non_apparies"],
        "dernier_rapport": {k: {kk: vv for kk, vv in v.items() if kk != "fiche"}
                            for k, v in sorted(r["par_ticker"].items())},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
