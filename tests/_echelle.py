"""Contrôles d'ÉCHELLE relatifs — pour les tests qui relisent les données publiées.

⚠️ POURQUOI CE MODULE EXISTE
────────────────────────────
Des tests de la famille « données publiées » portaient des seuils de prix
écrits en dur : `l52w > 250`, `ma200 > 300`, `l52w > 500`, `h52w < 2500`,
`0 < pb < 50`. Chacun protégeait un vrai défaut (un reliquat d'ancienne échelle,
le cours d'un autre titre) en le faisant dépendre du NIVEAU du marché au jour
où il avait été écrit. Le 08/10/2026, Sothema a fait un vrai plus-bas à 291 DH ;
le seuil à 250 était proche, un attendu daté a bloqué le run. Or la garde
pytest d'`update_bvc` est BLOQUANTE : un seuil de prix qui rougit sur un marché
sain empêche de publier.

⚠️ LE PRINCIPE, EN UNE PHRASE
Un reliquat d'échelle se reconnaît à une RUPTURE — deux clôtures successives
que la limite de ±10 % par séance (R10) rend impossibles —, jamais à un niveau
absolu. Une baisse RÉELLE, même de 60 %, est continue : chaque séance reste à
moins de 10 % de la précédente. Elle ne produit aucune rupture, donc ne
déclenche rien, où qu'elle porte le cours.

⚠️ CE QUE CE MODULE NE FAIT PAS
Il ne juge pas une valorisation et ne dit pas qu'un cours est « bon ». Il ne
voit pas non plus une série ENTIÈRE à la mauvaise échelle, sans aucune rupture :
ce cas se lit contre une source extérieure (bulletin, export de l'opérateur),
pas contre elle-même. Il ne s'applique pas à une référence remise à neuf par
l'autorité (R10, seconde précision : CMT après OPA) : une telle rupture est
LÉGITIME et se déclare dans le registre `SUSPENSIONS` — n'appliquer ces
contrôles qu'à des titres qui n'en portent pas.
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

# Limite réglementaire (R10) : ±10 % par séance, + 0,5 % pour l'arrondi du cours.
# ⚠️ Asymétrique : une baisse de 10 % est un rapport de 0,90 et non de 1/1,10 ;
# la borne symétrique en rapport marquait une limite-bas réelle comme rupture.
HAUSSE_SEANCE = 1.10 * 1.005
BAISSE_SEANCE = 0.90 * 0.995

# Facteur d'échelle des contaminations constatées, pour les titres dont le
# défaut est le cours D'UN AUTRE TITRE (et non un regroupement, que le registre
# SPLITS porte déjà). Chaque valeur est le rapport mesuré le jour du constat.
FACTEUR_CONTAMINATION = {
    "SNA": 28.0,   # Stokvis ~67 DH dans Sonasid ~1 900 DH (test_corrections_sonasid)
    "CIM": 3.7,    # Minière Touissit 5 940 DH dans Ciments du Maroc ~1 600 DH
    "STK": 7.4,    # table statique 490 DH dans Stokvis ~66 DH
}


# ── Lecture ────────────────────────────────────────────────────────────────

def charger_bougies(ticker: str) -> list:
    brut = json.loads((RACINE / "pipeline" / "candles" / f"{ticker}.json")
                      .read_text(encoding="utf-8"))
    return brut.get("candles", brut) if isinstance(brut, dict) else brut


def charger_cache(ticker: str) -> dict:
    return json.loads((RACINE / "pipeline" / "historical_data.json")
                      .read_text(encoding="utf-8"))[ticker]


def facteur_d_echelle(ticker: str) -> float:
    """Le facteur de l'opération ou de la contamination qui a fait le défaut.

    Il vient des registres, pas d'une constante de test : `SPLITS` pour un
    regroupement (Sothema ×5), le lot réceptionné pour un cours emprunté à un
    autre titre (MSA : médiane de corrigé ÷ remplacé), la table ci-dessus pour
    les autres.
    """
    import bvc_config
    facteurs = [1.0]
    facteurs += [float(s["ratio"]) for s in bvc_config.SPLITS.get(ticker, [])]
    if ticker in FACTEUR_CONTAMINATION:
        facteurs.append(FACTEUR_CONTAMINATION[ticker])
    if ticker == "MSA":
        doc = json.loads((RACINE / "datasets" / "corrections_acceptees" / "MSA.json")
                         .read_text(encoding="utf-8"))
        facteurs.append(statistics.median(
            max(l["corrige"]["c"] / l["remplace"]["c"],
                l["remplace"]["c"] / l["corrige"]["c"])
            for l in doc["lignes"]
            if l["corrige"]["c"] and l["remplace"]["c"]))
    return max(facteurs)


# ── Rupture et segments ────────────────────────────────────────────────────

def _jours_ouvres(a: str, b: str) -> int:
    d, fin, n = date.fromisoformat(a), date.fromisoformat(b), 0
    while d < fin:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return max(1, n)


def est_rupture(prec: dict, suiv: dict) -> bool:
    """Deux clôtures que R10 rend incompatibles, compte tenu des séances
    écoulées entre les deux dates (un trou dans la série élargit la borne)."""
    if not prec.get("c") or not suiv.get("c"):
        return False
    n = _jours_ouvres(prec["d"], suiv["d"])
    r = suiv["c"] / prec["c"]
    return r > HAUSSE_SEANCE ** n or r < BAISSE_SEANCE ** n


def segments(bougies: list) -> list:
    """Tronçons continus de la série, coupés à chaque rupture."""
    out, courant = [], []
    for b in bougies:
        if courant and est_rupture(courant[-1], b):
            out.append(courant)
            courant = []
        courant.append(b)
    if courant:
        out.append(courant)
    return out


def _reference(bougies: list):
    """Le tronçon de référence et sa médiane : le dernier, s'il porte au moins
    vingt séances — c'est le cours qu'on publie —, sinon le plus long."""
    segs = segments(bougies)
    dernier = segs[-1]
    ref = dernier if len(dernier) >= 20 else max(segs, key=len)
    return segs, ref, statistics.median(b["c"] for b in ref if b.get("c"))


def _melange(b: dict, seuil: float) -> bool:
    """Les quatre prix de la bougie ne tiennent pas dans une amplitude que R10
    autorise (rapport extrême/extrême > seuil = facteur/2)."""
    prix = [b[k] for k in ("o", "h", "l", "c") if b.get(k)]
    return bool(prix) and max(prix) / min(prix) > seuil


def hors_echelle(bougies: list, facteur: float) -> list:
    """Les bougies d'une AUTRE échelle que le cours publié.

    Deux formes de défaut, deux tests :
    - une bougie dont les quatre prix ne tiennent pas dans l'amplitude qu'une
      séance autorise (rapport extrême/extrême > facteur/2 : un plus-haut hérité
      de l'ancienne échelle sur une clôture de la nouvelle) ;
    - une bougie d'un tronçon COUPÉ du cours publié par une rupture, et dont le
      niveau s'écarte de plus de facteur/2 du tronçon de référence.

    Une baisse réelle, continue, ne produit ni l'une ni l'autre.
    """
    seuil = facteur / 2
    segs, ref, mediane = _reference(bougies)
    fautives = []
    for seg in segs:
        for b in seg:
            prix = [b[k] for k in ("o", "h", "l", "c") if b.get(k)]
            if not prix:
                continue
            melange = _melange(b, seuil)
            ailleurs = seg is not ref and (
                max(prix) / mediane > seuil or min(prix) < mediane / seuil)
            if melange or ailleurs:
                fautives.append(b["d"])
    return sorted(set(fautives))


def valeur_hors_echelle(valeur: float, bougies: list, facteur: float) -> bool:
    """Un extremum ou une moyenne publiés tiennent-ils à une autre échelle ?

    Dans la bande facteur/2 autour de la médiane du cours publié : non.
    Au-delà : seulement s'il n'est atteint par AUCUNE séance du tronçon continu
    qui porte le cours publié. Un vrai plus-bas, même très bas, est atteint par
    une séance de ce tronçon ; un reliquat vient d'un tronçon coupé.
    """
    seuil = facteur / 2
    _, ref, mediane = _reference(bougies)
    if mediane / seuil <= valeur <= mediane * seuil:
        return False
    # ⚠️ Une bougie MIXTE (ouverture et plus-bas d'un autre titre, clôture du
    # bon) n'atteint pas un extremum « réel » : sans cette exclusion, le 67,08
    # de Stokvis porté par l'ouverture d'une bougie de Sonasid se validait
    # lui-même.
    atteintes = {b[k] for b in ref if not _melange(b, seuil)
                 for k in ("o", "h", "l", "c") if b.get(k)}
    return valeur not in atteintes


# ── Les indicateurs du cache, recalculés depuis la série ───────────────────

def _fenetre(bougies: list, semaines: int, cle: str, jusqu_a: str) -> list:
    fin = date.fromisoformat(jusqu_a)
    debut = (fin - timedelta(weeks=semaines)).isoformat()
    return [b[cle] for b in bougies if debut <= b["d"] <= jusqu_a and b.get(cle)]


def cache_recalcule(bougies: list) -> dict:
    """Ce que le moteur doit publier pour cette série (bornes 52 semaines)."""
    dernier = bougies[-1]["d"]
    c = [b["c"] for b in bougies if b.get("c")]
    return {
        "l52w": min(_fenetre(bougies, 52, "l", dernier)),
        "h52w": max(_fenetre(bougies, 52, "h", dernier)),
        "ma200": round(sum(c[-200:]) / 200, 2) if len(c) >= 200 else None,
        "last_date": dernier,
    }


def defauts_extreme(nom: str, cache: dict, bougies: list, facteur: float) -> list:
    """`l52w` / `h52w` du cache : extremum d'une séance RÉELLE de la fenêtre,
    à l'échelle du cours publié. Ne dépend d'aucun niveau absolu."""
    cle = "l" if nom.startswith("l") else "h"
    valeur = cache[nom]
    # ⚠️ La série peut être EN AVANCE sur le cache (le moteur ajoute la séance du
    # jour, le cache est réécrit par un autre programme) : on juge le cache sur
    # la série ARRÊTÉE À SA DATE, sinon un vrai nouveau plus-bas de la dernière
    # séance ferait rougir un cache simplement un peu plus ancien.
    if cache.get("last_date"):
        bougies = [b for b in bougies if b["d"] <= cache["last_date"]]
    dernier = date.fromisoformat(bougies[-1]["d"])

    def fenetre(sem):
        return _fenetre(bougies, sem, cle, dernier.isoformat())

    defauts = []
    # Bornes larges d'une semaine de part et d'autre : le moteur date sa
    # fenêtre du jour d'analyse, le test de la dernière bougie.
    if valeur not in fenetre(53):
        defauts.append(f"{nom} = {valeur} n'est l'extremum d'aucune séance de l'année")
    extreme = min if cle == "l" else max
    if fenetre(51) and (extreme(fenetre(51)) < valeur if cle == "l"
                        else extreme(fenetre(51)) > valeur):
        defauts.append(f"une séance récente dépasse l'extremum publié {valeur}")
    if valeur_hors_echelle(valeur, bougies, facteur):
        defauts.append(f"{nom} = {valeur} est à une autre échelle que le cours "
                       f"(facteur {facteur:g}) et aucune séance du tronçon "
                       "courant ne l'atteint")
    return defauts


def defauts_moyenne(cache: dict, bougies: list, tolerance: float = 0.01) -> list:
    """`ma200` du cache = moyenne des 200 dernières clôtures jusqu'à la date du
    cache (pas jusqu'à aujourd'hui : le moteur peut être en avance sur lui)."""
    if cache.get("ma200") is None:
        return []
    cl = [b["c"] for b in bougies
          if b["d"] <= cache["last_date"] and b.get("c")][-200:]
    attendu = sum(cl) / len(cl)
    if abs(cache["ma200"] / attendu - 1) > tolerance:
        return [f"ma200 du cache {cache['ma200']} contre {attendu:.2f} recalculé "
                f"sur la série (écart > {tolerance:.0%})"]
    return []


# ── Fabrication de séries pour les contrôles ───────────────────────────────

def prolonger(bougies: list, cible: float, pas: float = 0.09) -> list:
    """Prolonge la série par une trajectoire CONTINUE jusqu'à `cible` (clôture),
    chaque séance restant à moins de `pas` de la précédente (R10). C'est la
    forme d'une vraie baisse ou d'une vraie hausse : sans rupture."""
    out = [dict(b) for b in bougies]
    d = date.fromisoformat(out[-1]["d"])
    c = out[-1]["c"]
    while abs(c / cible - 1) > 1e-9:
        nouveau = min(c * (1 + pas), cible) if cible > c else max(c * (1 - pas), cible)
        nouveau = round(nouveau, 2)
        d += timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append({"d": d.isoformat(), "o": c, "h": max(c, nouveau),
                    "l": min(c, nouveau), "c": nouveau, "v": 1000})
        if nouveau == cible:
            break
        c = nouveau
    return out


def diviser(bougies: list, debut: int, fin: int, facteur: float) -> list:
    """Réinjecte un reliquat : les bougies [debut:fin] ramenées d'un facteur."""
    out = [dict(b) for b in bougies]
    for b in out[debut:fin]:
        for k in ("o", "h", "l", "c"):
            if b.get(k):
                b[k] = round(b[k] / facteur, 2)
    return out


# ── Ratios de valorisation : l'échelle se lit contre les AUTRES titres ─────

# Un P/B réel de la place s'étage de 0,16 à 6 fois la médiane (relevé du
# 11/10/2026, 46 titres) ; une erreur d'unité (MMAD pris pour des dirhams, deux
# colonnes recollées) est un facteur 1 000. La bande ×20 laisse trois fois la
# marge aux vrais extrêmes et attrape le facteur mille de très loin.
BANDE_COUPE_TRANSVERSALE = 20.0


def ratios_hors_echelle(valeurs: dict, bande: float = BANDE_COUPE_TRANSVERSALE) -> list:
    """Titres dont le ratio est nul, négatif, ou hors de [médiane/bande,
    médiane×bande] de la place.

    ⚠️ Contrairement à `0 < pb < 50`, la bande suit le marché : si toute la
    place valorise deux fois plus cher, la médiane suit et rien ne rougit. Seul
    un titre ISOLÉ de son univers par un facteur 20 est signalé. Limite
    assumée : une erreur d'unité qui toucherait la place entière à la fois
    passerait — elle se lit contre les rapports déposés, pas contre elle-même.
    """
    positifs = [v for v in valeurs.values() if v is not None and v > 0]
    fautifs = [f"{t} : {v}" for t, v in sorted(valeurs.items())
               if v is not None and v <= 0]
    if len(positifs) < 5:
        return fautifs
    mediane = statistics.median(positifs)
    fautifs += [f"{t} : {v} (médiane de la place {mediane:.2f})"
                for t, v in sorted(valeurs.items())
                if v is not None and v > 0
                and not (mediane / bande <= v <= mediane * bande)]
    return fautifs
