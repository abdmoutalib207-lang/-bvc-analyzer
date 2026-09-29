#!/usr/bin/env python3
"""Les dépôts de résultats, lus à la source : la liste des communiqués AMMC.

⚠️ POURQUOI CE MODULE — 29/09/2026
──────────────────────────────────
Le détecteur de comptes récents (`fondamentaux_frais.py`) ne voyait que les
publications que le collecteur d'actualités avait ÉTIQUETÉES avec un code de
titre. Relevé ce soir-là sur les 15 dernières pages de l'AMMC : 58 dépôts de
résultats semestriels, dont une douzaine de NOS titres jamais signalés —
CMGP et Vicenne (MASI 1), Salafin, AFMA, Agma, BMCI, Fenie Brossette,
Holcim, SBM, SNEP, Taqa, Mutandis. Et l'étiquetage se trompait aussi dans
l'autre sens : trois articles sur les « alliances » politiques d'après les
élections étaient rattachés à Alliances (ADI).

On lit donc la liste du régulateur elle-même. Chaque entrée porte une date,
un titre « Émetteur - objet » et le lien du dépôt.

⚠️ L'IDENTITÉ NE SE DEVINE PAS
Trois voies, et aucune ressemblance de noms :
  1. `ammc_etats_financiers.resoudre()` — code entre parenthèses posé par
     l'émetteur, ou nom normalisé en correspondance ENTIÈRE ;
  2. un nom égal à un CODE OFFICIEL BVC de `IDB_TICKER_MAP` (« SBM » est
     notre SBS, « BCP », « CMT », « SMI ») — vérifié sans doublon ;
  3. `ALIAS_AMMC` pour les trois noms que l'AMMC écrit autrement que nous.
Un émetteur qui ne passe aucune voie est IGNORÉ : Autoroutes du Maroc, OCP,
TMPA, Saham Bank… émettent des obligations, pas des actions cotées.

    python pipeline/depots_ammc.py        # met à jour pipeline/depots_ammc.json
"""

from __future__ import annotations

import html as _html
import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

BASE = "https://www.ammc.ma"
LISTE = BASE + "/fr/communiques-presse-emetteurs"
CACHE = Path(__file__).parent / "depots_ammc.json"
UA = "BVC-Analyzer/1.0 (recherche quantitative; contact via le dépôt GitHub)"
# Dix entrées par page. Huit pages couvrent les jours de rush de fin de
# semestre (≈ 60 dépôts en deux jours relevés le 29/09) ; le cache accumule
# ce qui a déjà été vu, donc un passage manqué ne perd rien.
PAGES = 8
PAUSE = 0.4
CONSERVES = 600

# Noms que l'AMMC écrit autrement que notre référentiel. Chacun relevé sur la
# liste du 29/09/2026 et rapproché du titre coté correspondant.
ALIAS_AMMC = {
    "eqdom": "EQD",          # « Eqdom » — notre « Crédit Eqdom »
    "labelvie": "LBV",       # « LabelVie » — notre « Label Vie »
    "marsa maroc": "MSA",    # « Marsa Maroc » — notre « Sodep-Marsa Maroc »
}

# ⚠️ « indicateurs » N'EN FAIT PAS PARTIE. Relevé le 29/09 sur RDS : « CP
# relatif aux indicateurs du 2ème trimestre 2026 » donne un chiffre d'affaires
# trimestriel, pas des comptes. Le compter comme un dépôt de résultats
# signalerait « comptes plus récents publiés » là où il n'y en a aucun.
_RESULTATS = re.compile(r"(?i)r[ée]sultats|rapport financier|\bRFS\b|profit warning")
_AVERTISSEMENT = re.compile(r"(?i)profit warning|avertissement")


def parser_page(page: str) -> list[dict]:
    """Les entrées d'une page de la liste. Fonction pure."""
    out = []
    for li in re.findall(r'<li class="actualites-row">(.*?)</li>', page, flags=re.S):
        d = re.search(r'datetime="(\d{4}-\d{2}-\d{2})', li)
        t = re.search(r'views-field-title"><span class="field-content">(.*?)</span>', li, flags=re.S)
        u = re.search(r'href="([^"]+\.pdf)"', li)
        if not (d and t):
            continue
        titre = " ".join(_html.unescape(re.sub(r"<[^>]+>", "", t.group(1))).split())
        out.append({"date": d.group(1), "titre": titre,
                    "url": (BASE + u.group(1)) if u and u.group(1).startswith("/") else (u.group(1) if u else None)})
    return out


def emetteur(titre: str) -> str:
    return titre.split(" - ")[0].strip()


def resoudre_emetteur(nom: str) -> str | None:
    """Notre ticker pour un nom d'émetteur AMMC, ou None."""
    from pipeline.ammc_etats_financiers import normaliser, resoudre
    from bvc_config import IDB_TICKER_MAP
    t = resoudre(nom)
    if t:
        return t
    officiels = {v: k for k, v in IDB_TICKER_MAP.items() if v}
    if nom.strip() in officiels:
        return officiels[nom.strip()]
    return ALIAS_AMMC.get(normaliser(nom))


def depots_par_ticker(entrees: list[dict]) -> dict:
    """{ticker: le dépôt de résultats le plus récent}. Fonction pure.

    Un avertissement sur résultats (« profit warning ») est signalé comme tel :
    il annonce des comptes, il n'en contient pas.
    """
    out: dict[str, dict] = {}
    for e in entrees:
        if not _RESULTATS.search(e.get("titre") or ""):
            continue
        t = resoudre_emetteur(emetteur(e["titre"]))
        if not t:
            continue
        if t in out and out[t]["date"] >= e["date"]:
            continue
        out[t] = {"date": e["date"], "titre": e["titre"], "url": e.get("url"),
                  "source": "AMMC — liste des communiqués des émetteurs",
                  **({"avertissement": True} if _AVERTISSEMENT.search(e["titre"]) else {})}
    return out


def _lire(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=30) as r:  # noqa: S310 — URL fixe du régulateur
        return r.read().decode("utf-8", "ignore")


def collecter(pages: int = PAGES, lire=_lire, pause: float = PAUSE) -> list[dict]:
    """Les entrées des `pages` premières pages, plus récentes d'abord."""
    out = []
    for p in range(pages):
        out.extend(parser_page(lire(f"{LISTE}?page={p}")))
        if pause:
            time.sleep(pause)
    return out


def fusionner(anciennes: list[dict], nouvelles: list[dict]) -> list[dict]:
    """Accumule sans doublon (clé : lien du dépôt, sinon titre + date)."""
    vus, out = set(), []
    for e in sorted(nouvelles + anciennes, key=lambda z: z["date"], reverse=True):
        k = e.get("url") or (e["titre"], e["date"])
        if k in vus:
            continue
        vus.add(k)
        out.append(e)
    return out[:CONSERVES]


def charger() -> list[dict]:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8")).get("entrees") or []
    except (OSError, ValueError):
        return []


def mettre_a_jour(lire=_lire) -> list[dict]:
    entrees = fusionner(charger(), collecter(lire=lire))
    CACHE.write_text(json.dumps({"source": LISTE, "entrees": entrees},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    return entrees


if __name__ == "__main__":
    e = mettre_a_jour()
    d = depots_par_ticker(e)
    print(f"{len(e)} entrées ; {len(d)} titres avec un dépôt de résultats : {', '.join(sorted(d))}")
