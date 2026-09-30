#!/usr/bin/env python3
"""Ce que la séance a été, au-delà de sa clôture — relevé le jour même.

⚠️ POURQUOI CE MODULE — 30/09/2026
──────────────────────────────────
Un briefing rédigé par un autre assistant pour la séance du 29/09 disait trois
choses que le nôtre ne savait pas dire :

  · la TRAJECTOIRE de l'indice — ouverture, plus haut, plus bas, clôture, et
    ce que la séance a fait entre les deux ;
  · la tenue des SECTEURS ;
  · le contexte des MATIÈRES PREMIÈRES.

Il les disait sans source ni horodatage. Ce module les MESURE, et chaque valeur
porte son origine et sa date.

⚠️ POURQUOI UN FICHIER, ET POURQUOI LE JOUR MÊME
La série intrajournalière de CDG (`INDICE-O-GRAPH-INTRA`) ne vit qu'une
journée. Relevé le 30/09 à 08h46 : elle ne contenait plus qu'UN point, daté du
30/09 à 08:03 et portant la clôture du 29. La trajectoire du 29 avait disparu.
Elle doit donc être relevée par les passages de 15h45 et 18h45 et conservée
dans `pipeline/seance_marche.json` ; le lendemain, il est trop tard.

⚠️ LES SOURCES, ET CE QUI A ÉTÉ VÉRIFIÉ LE 30/09/2026
  CDG Capital Bourse  `INDICE-O-GRAPH-INTRA` et `INDICE-SYNTHESE`, paramètres
                      lus dans le code du site (main.c09bc1b4.js), HTTP 200
                      avec un User-Agent qui dit qui nous sommes.
  indices sectoriels  les CODES viennent du fournisseur lui-même (sa recherche
                      `QUICK-SEARCH`), jamais devinés : un code inconnu
                      renvoie une réponse VALIDE aux champs vides (piège déjà
                      rencontré sur `MASI20`, voir `_ligne_indice_cdg`).
  TradingView         scanner public `futures`, HTTP 200 sans authentification
                      avec le même User-Agent honnête. `update_time` date
                      chaque valeur ; sans lui, la valeur n'est pas publiée.

⚠️ CE QUI A ÉTÉ ÉCARTÉ, ET POURQUOI
  · les matières premières de CDG (`COMMODITIES`, `METALS`) : aucune date dans
    la charge utile. Le 30/09 à 08h46 elles donnaient le Brent à 89,44 (+6,84 %)
    quand le contrat Brent le plus proche cotait 96,39 (+0,24 %) chez
    TradingView. Une valeur sans date ne se vérifie pas.
  · `INDICE-SESSIONS` : a répondu des séances d'AOÛT 2025 pour le MASI.
  · `SAC`, `AGR`, `EEE` : listés par la recherche du fournisseur, mais
    `INDICE-SYNTHESE` les renvoie creux. Non interrogés.

⚠️ AUCUN SCORE N'EN DÉPEND (R8). C'est une couche de lecture.
⚠️ AUCUNE CAUSE N'EN EST TIRÉE. Qu'un secteur ait monté et que le Brent ait
monté le même jour est une coïncidence de dates, pas une explication.

    python pipeline/seance_marche.py AAAA-MM-JJ   # relevé à la main
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CHEMIN = RACINE / "pipeline" / "seance_marche.json"

CDG_API = "https://www.cdgcapitalbourse.ma/api/"
CDG_REFERER = "https://www.cdgcapitalbourse.ma/Bourse/market"
TV_SCANNER = "https://scanner.tradingview.com/futures/scan"
# ⚠️ Un User-Agent qui dit qui nous sommes. Si une source le refuse, on ne
# se déguise pas en navigateur pour passer : on s'en passe, et on le dit.
UA = "BVC-Analyzer/1.0 (contrôle de cohérence des indicateurs)"

# Séances conservées. Soixante couvrent trois mois de cotation, bien plus que
# ce que le briefing relit (la veille) ; au-delà, le fichier ne sert plus.
CONSERVEES = 60

# L'ouverture officielle de la Bourse de Casablanca, à l'heure de CDG.
# ⚠️ Mesuré le 30/09 : avant elle, la série porte un point de pré-ouverture
# (08:03) qui recopie la clôture de la VEILLE. Le prendre pour l'ouverture
# annoncerait une séance ouverte « à plat » tous les jours.
OUVERTURE_HHMM = "09:30"

# ⚠️ LES INDICES SECTORIELS : codes relevés le 30/09/2026 par la recherche du
# fournisseur (`QUICK-SEARCH`, type « I »), chacun vérifié en interrogeant
# `INDICE-SYNTHESE` : le `Symbol` renvoyé égale le code, le `Libelle` est
# servi, `DateCotation` porte la séance. Quatre recoupés au titre près avec nos
# cours du 29/09, sur les secteurs à une seule valeur :
#     TCOM  −0,29 %  = IAM −0,29 %      S&P   −3,72 %  = MDP −3,72 %
#     SDT   −0,12 %  = MSA −0,12 %      ELEC   0,00 %  = TQA  0,00 %
SECTEURS_CDG = (
    "BANK", "B&MC", "IMMOB", "SPI", "ASSUR", "MINES", "TCOM", "AGRO", "P&G",
    "DISTR", "L&SI", "SDT", "PHARM", "I&BEI", "CHIM", "ELEC", "SF&AF", "SP&H",
    "TRANS", "SANTE", "L&H", "BOISS", "S&P",
)

# ⚠️ LES MATIÈRES PREMIÈRES : le contrat à terme le plus proche (`1!`), choix
# d'Abd Moutalib pour la source. Le NOM affiché est celui que TradingView sert
# (`description`), jamais une traduction de notre cru ; la devise aussi.
MATIERES_TV = (
    ("ICEEUR:BRN1!", "Brent"),
    ("NYMEX:CL1!", "WTI"),
    ("COMEX:GC1!", "Or"),
    ("NYMEX:NG1!", "Gaz naturel (Henry Hub)"),
    ("CBOT:ZW1!", "Blé (Chicago)"),
)
COLONNES_TV = ("description", "close", "change", "currency", "update_time",
               "update_mode")


# ── Lecture des réponses — fonctions pures ─────────────────────────────────

def _n(v):
    if v is None or isinstance(v, bool) or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def _date_cdg(brut) -> str | None:
    """« 29/09/2026 08:03:01 » → « 2026-09-29 ». Rien d'autre n'en est tiré."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", str(brut or ""))
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def _heure_cdg(brut) -> str | None:
    m = re.match(r"\d{2}/\d{2}/\d{4} (\d{2}):(\d{2})", str(brut or ""))
    return f"{m.group(1)}:{m.group(2)}" if m else None


def actions_cdg(secteurs=SECTEURS_CDG) -> list:
    """Le corps de la requête : synthèse et série du MASI, puis les secteurs."""
    def act(nom, params):
        return {"ACTION": {"NAME": nom, "TYPE": "SELECT", "VALUE": nom},
                "PARAMS": [{"NAME": k, "TYPE": t, "VALUE": v} for k, t, v in params]}
    base = [("Lang_", "S", "fr"), ("Espace_", "I", "1"), ("IdPartener_", "I", "1")]
    out = [act("INDICE-SYNTHESE", base + [("Indice_", "S", "MASI")]),
           # ⚠️ `Lang_` vaut « XX » pour la série : c'est ce que le site envoie.
           act("INDICE-O-GRAPH-INTRA", [("Lang_", "S", "XX"), ("Espace_", "I", "1"),
                                        ("IdPartener_", "I", "1"),
                                        ("Indice_", "S", "MASI")])]
    out += [act("INDICE-SYNTHESE", base + [("Indice_", "S", c)]) for c in secteurs]
    return out


def lire_cdg(reponse, secteurs=SECTEURS_CDG) -> dict:
    """{"masi": ligne | None, "intra": [points], "secteurs": {code: ligne}}.

    ⚠️ Les blocs sont appariés par POSITION à la requête, comme le fait le
    site. C'est pourquoi l'identité est revérifiée ensuite sur chaque ligne :
    un bloc décalé porterait un autre `Symbol`.
    """
    out = {"masi": None, "intra": [], "secteurs": {}}
    if not isinstance(reponse, list) or len(reponse) < 2:
        return out

    def data(bloc, nom):
        b = (bloc or {}).get(nom) or {}
        return (b.get("Data") or []) if b.get("Valid") else []

    m = data(reponse[0], "INDICE-SYNTHESE")
    out["masi"] = m[0] if m else None
    out["intra"] = data(reponse[1], "INDICE-O-GRAPH-INTRA")
    for code, bloc in zip(secteurs, reponse[2:]):
        d = data(bloc, "INDICE-SYNTHESE")
        if d:
            out["secteurs"][code] = d[0]
    return out


def trajectoire(masi: dict | None, points: list, seance: str) -> dict | None:
    """La séance de l'indice : ouverture, extrêmes et clôture. Fonction pure.

    ⚠️ QUATRE REFUS, chacun pour une raison mesurée :
      · l'identité — `Symbol` doit valoir MASI et la synthèse être DATÉE de la
        séance, comme dans `fetch_masi_cdg` ;
      · la date des points — le lendemain matin, la série porte un point daté
        du jour qui recopie la clôture de la veille (relevé le 30/09 à 08h46) ;
      · la pré-ouverture — le point de 08:03 n'est pas une cotation ;
      · la concordance — le dernier point de la série doit REDONNER le cours
        de la synthèse. Deux voies indépendantes, un seul chiffre ; sinon la
        série n'est pas celle de la séance publiée.

    ⚠️ LES EXTRÊMES SONT CEUX DE LA SYNTHÈSE, PAS CEUX DE LA SÉRIE. La série
    est échantillonnée : son maximum peut manquer le vrai plus haut. L'HEURE
    d'un extrême n'est donc publiée que si la série atteint EXACTEMENT la
    valeur officielle ; sinon elle est déclarée inconnue, jamais approchée.
    """
    if not masi or str(masi.get("Symbol") or "") != "MASI":
        return None
    if _date_cdg(masi.get("DateCotation")) != seance:
        return None
    cours, veille = _n(masi.get("Cours")), _n(masi.get("CoursVeille"))
    haut, bas = _n(masi.get("PlusHaut")), _n(masi.get("PlusBas"))
    if None in (cours, veille, haut, bas):
        return None

    serie = []
    for p in points or []:
        c = _n(p.get("Cours"))
        h = _heure_cdg(p.get("HoroDatage"))
        if c is None or h is None or _date_cdg(p.get("HoroDatage")) != seance:
            continue
        if h < OUVERTURE_HHMM:
            continue
        serie.append((h, c))
    serie.sort()
    if not serie:
        return None
    # ⚠️ Tolérance d'un dix-millième de point : la synthèse et la série sont
    # servies à quatre décimales par le même fournisseur.
    if abs(serie[-1][1] - cours) > 1e-4:
        return None

    def heure_de(valeur):
        for h, c in serie:
            if abs(c - valeur) <= 1e-4:
                return h
        return None

    ouverture = serie[0]
    return {
        "seance": seance,
        "veille": round(veille, 4),
        "ouverture": round(ouverture[1], 4),
        "heure_ouverture": ouverture[0],
        "plus_haut": round(haut, 4), "heure_plus_haut": heure_de(haut),
        "plus_bas": round(bas, 4), "heure_plus_bas": heure_de(bas),
        "cloture": round(cours, 4),
        "heure_dernier_point": serie[-1][0],
        "n_points": len(serie),
        "source": "CDG Capital Bourse — INDICE-SYNTHESE et INDICE-O-GRAPH-INTRA (MASI)",
    }


def secteurs(lignes: dict, seance: str) -> list:
    """Les indices sectoriels de la séance, du plus fort au plus faible.

    ⚠️ Une ligne n'est retenue que si le fournisseur confirme SON identité
    (`Symbol` = code demandé, `Libelle` servi) et la DATE de la séance. Un code
    inconnu renvoie des champs vides sans erreur : sans ce contrôle, un
    secteur creux s'afficherait à 0,00 %, ce qui est une mesure — fausse.
    """
    out = []
    for code, x in (lignes or {}).items():
        if str(x.get("Symbol") or "") != code or not x.get("Libelle"):
            continue
        if _date_cdg(x.get("DateCotation")) != seance:
            continue
        v, c, cv = _n(x.get("VariationP")), _n(x.get("Cours")), _n(x.get("CoursVeille"))
        if v is None or c is None:
            continue
        out.append({"code": code, "libelle": str(x["Libelle"]).strip(),
                    "variation_pct": round(v, 2), "cours": round(c, 4),
                    "cours_veille": round(cv, 4) if cv is not None else None})
    return sorted(out, key=lambda z: (-z["variation_pct"], z["code"]))


def matieres(reponse, attendus=MATIERES_TV, colonnes=COLONNES_TV) -> list:
    """Les matières premières, chacune avec l'HORODATAGE de sa valeur.

    ⚠️ JAMAIS DE VALEUR SANS DATE. Une ligne sans `update_time` est écartée,
    même si son cours est servi. Et le mode de diffusion est recopié tel quel :
    `delayed_streaming_600` veut dire que la source déclare un différé de
    600 secondes — ce n'est pas à nous de le traduire en « temps réel ».
    """
    if not isinstance(reponse, dict):
        return []
    lignes = {x.get("s"): x.get("d") for x in reponse.get("data") or []
              if isinstance(x, dict)}
    idx = {c: i for i, c in enumerate(colonnes)}
    out = []
    for ticker, nom in attendus:
        d = lignes.get(ticker)
        if not isinstance(d, list) or len(d) != len(colonnes):
            continue
        valeur, var = _n(d[idx["close"]]), _n(d[idx["change"]])
        ts = _n(d[idx["update_time"]])
        if valeur is None or ts is None or ts <= 0:
            continue
        out.append({
            "ticker": ticker, "nom": nom,
            "description_source": d[idx["description"]],
            "valeur": valeur,
            "variation_pct": round(var, 2) if var is not None else None,
            "devise": d[idx["currency"]],
            "horodatage_utc": datetime.fromtimestamp(ts, timezone.utc)
                                      .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mode_source": d[idx["update_mode"]],
            "source": "TradingView — scanner futures, contrat le plus proche",
        })
    return out


def fusionner(ancien: dict | None, nouveau: dict, seance: str,
              aujourd_hui: str) -> dict:
    """L'entrée de la séance après ce passage. Fonction pure.

    ⚠️ DEUX RÈGLES :
      · un champ déjà relevé n'est JAMAIS remplacé par un vide. Le passage du
        lendemain matin trouve une série qui ne porte plus la séance : il ne
        doit pas effacer la trajectoire relevée la veille ;
      · les matières premières ne se relèvent que LE JOUR DE LA SÉANCE. Un
        passage de 9h45 le lendemain lirait des cours de la nuit suivante et
        les rangerait sous une séance qu'ils ne décrivent pas.
    """
    e = dict(ancien or {})
    for k in ("trajectoire", "secteurs"):
        if nouveau.get(k):
            e[k] = nouveau[k]
    if seance == aujourd_hui and nouveau.get("matieres"):
        e["matieres"] = nouveau["matieres"]
    return e


# ── Réseau ─────────────────────────────────────────────────────────────────

def _post(url, corps, entetes):
    import requests
    r = requests.post(url, json=corps, timeout=30,
                      headers={"User-Agent": UA, "Content-Type": "application/json",
                               **entetes})
    if r.status_code != 200:
        raise RuntimeError(f"{url} : HTTP {r.status_code}")
    return r.json()


def poster_cdg(actions):
    return _post(CDG_API, {"ACTIONS": actions},
                 {"Referer": CDG_REFERER, "Origin": "https://www.cdgcapitalbourse.ma"})


def poster_tv(tickers, colonnes=COLONNES_TV):
    return _post(TV_SCANNER, {"symbols": {"tickers": list(tickers), "query": {"types": []}},
                              "columns": list(colonnes)}, {})


def charger(chemin=None) -> dict:
    try:
        d = json.loads(Path(chemin or CHEMIN).read_text(encoding="utf-8"))
        return d.get("seances") or {}
    except (OSError, ValueError, AttributeError):
        return {}


def mettre_a_jour(seance: str, aujourd_hui: str, chemin=None,
                  cdg=poster_cdg, tv=poster_tv) -> dict:
    """Relève la séance et l'écrit. Renvoie l'entrée de la séance.

    ⚠️ Chaque source est indépendante : l'échec de l'une n'empêche pas l'autre,
    et aucun échec ne lève — le briefing dit ce qui manque.
    """
    nouveau = {}
    try:
        lu = lire_cdg(cdg(actions_cdg()))
        nouveau["trajectoire"] = trajectoire(lu["masi"], lu["intra"], seance)
        nouveau["secteurs"] = secteurs(lu["secteurs"], seance)
    except Exception as e:                                # noqa: BLE001
        print(f"  seance_marche : CDG indisponible ({e})", file=sys.stderr)
    try:
        nouveau["matieres"] = matieres(tv([t for t, _ in MATIERES_TV]))
    except Exception as e:                                # noqa: BLE001
        print(f"  seance_marche : TradingView indisponible ({e})", file=sys.stderr)

    p = Path(chemin or CHEMIN)
    seances = charger(p)
    seances[seance] = fusionner(seances.get(seance), nouveau, seance, aujourd_hui)
    garde = dict(sorted(seances.items())[-CONSERVEES:])
    p.write_text(json.dumps({
        "_note": "Trajectoire du MASI, indices sectoriels (CDG) et matières "
                 "premières (TradingView), relevés le jour de la séance. Voir "
                 "pipeline/seance_marche.py.",
        "seances": garde}, ensure_ascii=False, indent=1), encoding="utf-8")
    return garde.get(seance) or {}


if __name__ == "__main__":
    sys.path.insert(0, str(RACINE))
    from bvc_config import heure_maroc  # noqa: E402
    s = sys.argv[1] if len(sys.argv) > 1 else heure_maroc().date().isoformat()
    e = mettre_a_jour(s, heure_maroc().date().isoformat())
    print(json.dumps(e, ensure_ascii=False, indent=1))
