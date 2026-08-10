#!/usr/bin/env python3
"""
Lecture des bulletins « Indices » de CDG Capital Bourse.

Pourquoi cette source : IDBourse tombe (blocage de provenance du 05/08/2026),
Médias24 refuse les IP qui ne sont pas marocaines, et le référentiel officiel
BVC n'est pas librement interrogeable. Le bulletin CDG, lui, est publié chaque
jour de séance et couvre toute la cote. Il a servi de juge de paix le
10/08/2026 : concordance 67/67 avec le previous_close de casabourse.app.

Deux variantes de bulletin, toutes deux reconnues ici :

  « cotations » — une ligne par instrument :
        libelle Cours variation pto Ouverture QteEchangee Volumes
        PlusHaut PlusBas date
  « DataChart » — mêmes colonnes plus la série des 30 dernières clôtures,
        séparées par des points-virgules et closes par « |G ».

⚠️ Trois pièges, tous rencontrés en production :

1. **Le titre porte la date de PUBLICATION, pas celle de la séance.**
   « Indices du lundi 10 août » contient la séance du vendredi 07/08. Ne
   jamais déduire la date des cours du nom du fichier — la fonction
   `date_seance()` la lit dans les horodatages, qui sont ceux des échanges.

2. **Les codes sont les tickers officiels BVC, pas les nôtres.**
   SID = Sonasid, SNA = Stokvis, ZDJ = Zellidja. Passer par `IDB_TICKER_MAP`
   avant toute comparaison, sinon Sonasid hérite du cours de Stokvis.

3. **Les montants groupent les milliers par espaces, la quantité échangée
   non.** Sans distinction, « 3 652.00 546 2 009 253.00 » se recolle en un
   seul nombre et toutes les colonnes glissent d'un cran. D'où le motif
   `_MONTANT`, qui exige deux décimales.

La variante DataChart n'expose pas de lignes exploitables : son texte est
extrait colonne par colonne, verticalement, et les libellés en ressortent
tronqués (« UTctionT » pour Mutandis). Elle ne se lit donc qu'accompagnée du
bulletin de cotations du même jour, qui fournit la table clôture → instrument
servant à réattribuer les séries. Passer les deux fichiers ensemble.

Usage :
    python3 pipeline/parse_cdg_bulletin.py cotations.pdf                 # aperçu
    python3 pipeline/parse_cdg_bulletin.py cotations.pdf datachart.pdf   # + séries
    python3 pipeline/parse_cdg_bulletin.py *.pdf --json releve.json
    python3 pipeline/parse_cdg_bulletin.py *.pdf --verifier 2026-08-07
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from bvc_config import IDB_TICKER_MAP, ISIN_MAP, COMPANY_NAMES  # noqa: E402

RACINE = Path(__file__).parent.parent
CANDLES = Path(__file__).parent / "candles"

# ticker officiel BVC → le nôtre
TICKER_BVC = {idb: nous for nous, idb in IDB_TICKER_MAP.items()}

# Un montant : milliers séparés par des espaces (ordinaire ou insécable),
# toujours deux décimales. La quantité échangée, elle, est un entier nu.
_MONTANT = r'(?:\d{1,3}(?:[   ]\d{3})*|\d+)\.\d{2}'
_LIGNE = re.compile(
    rf'^([A-Z0-9]{{2,5}})\s+({_MONTANT})\s+(-?\d+(?:\.\d+)?)\s+-\s+({_MONTANT})'
    rf'\s+(\d+|-)\s+({_MONTANT})\s+({_MONTANT})\s+({_MONTANT})\s+(\S+)$')
_SERIE = re.compile(r'(?:\d+\.?\d*;){9,}\d+\.?\d*')
_HEURE = re.compile(r'\b([01]\d|2[0-3]):[0-5]\d:[0-5]\d\b')


def _texte(pdf: Path) -> str:
    import pdfplumber
    with pdfplumber.open(pdf) as doc:
        return "\n".join(p.extract_text() or "" for p in doc.pages)


def _nombre(s: str) -> float:
    return float(re.sub(r'[   ]', '', s))


def parse_cotations(pdf: Path) -> dict:
    """{ code officiel BVC : {cours, var, ouverture, qte, volume, haut, bas} }.

    Les instruments non traités de la séance sortent à 0.00 dans le bulletin ;
    ils sont conservés tels quels, à charge de l'appelant de les ignorer — un
    cours nul veut dire « pas d'échange », pas « valeur inconnue ».
    """
    out = {}
    for ligne in _texte(pdf).splitlines():
        m = _LIGNE.match(ligne.strip())
        if not m:
            continue
        code, c, var, o, q, vol, hi, lo, heure = m.groups()
        out[code] = {
            "cours": _nombre(c), "var": float(var), "ouverture": _nombre(o),
            "qte": int(q) if q.isdigit() else 0, "volume": _nombre(vol),
            "haut": _nombre(hi), "bas": _nombre(lo), "heure": heure,
        }
    return out


def parse_series(pdf: Path, cotations: dict) -> dict:
    """{ code officiel BVC : [clôtures, de la plus ancienne à la séance du jour] }.

    L'extraction PDF entrelace les colonnes et rend le libellé peu fiable —
    on a vu « 15RDS » et « GWAA » sortir du texte brut. On apparie donc chaque
    série à son instrument par sa DERNIÈRE valeur, qui est la clôture de la
    séance, connue sans ambiguïté par `cotations`. Une série dont la dernière
    valeur correspond à plusieurs instruments est écartée.
    """
    par_cloture = {}
    for code, v in cotations.items():
        if v["cours"]:
            par_cloture.setdefault(round(v["cours"], 2), []).append(code)

    texte = re.sub(r'\s+', '', _texte(pdf))
    out = {}
    for brut in _SERIE.findall(texte):
        vals = [float(x) for x in brut.split(';') if x]
        # La première valeur mord souvent sur l'horodatage qui la précède
        # (« 15:40:39 » + « 91.70 » → « 3991.70 ») : on l'écarte par principe.
        cands = par_cloture.get(round(vals[-1], 2))
        if cands and len(cands) == 1:
            garde = out.get(cands[0])
            if garde is None or len(vals) > len(garde):
                out[cands[0]] = vals[1:]
    return out


def date_seance(pdf: Path) -> str | None:
    """Heure du dernier échange — sert à repérer une séance, pas à la dater.

    Le titre du bulletin porte la date de publication : « Indices du lundi
    10 août » contient la séance du vendredi 07/08. Cette fonction ne rend
    donc que l'heure la plus tardive observée, comme indice de séance réelle
    (une séance BVC ferme à 15h30) ; la date, elle, doit venir de l'appelant.
    """
    heures = _HEURE.findall(_texte(pdf))
    return max(_HEURE.finditer(_texte(pdf)), key=lambda m: m.group(0)).group(0) \
        if heures else None


def vers_nos_tickers(donnees: dict) -> dict:
    """Traduit les codes officiels BVC vers les nôtres, en écartant l'inconnu."""
    out = {}
    for code, v in donnees.items():
        t = TICKER_BVC.get(code, code)
        if t in ISIN_MAP:
            out[t] = v
    return out


def comparer(cotations: dict, date: str) -> list:
    """Écarts entre le bulletin et nos chandelles, pour la séance `date`."""
    ecarts = []
    for t, v in sorted(vers_nos_tickers(cotations).items()):
        f = CANDLES / f"{t}.json"
        if not v["cours"] or not f.exists():
            continue
        bougies = json.loads(f.read_text(encoding="utf-8"))
        jour = next((k for k in bougies if k.get("d") == date), None)
        if not jour or not jour.get("c"):
            continue
        e = (v["cours"] - jour["c"]) / v["cours"] * 100
        if abs(e) > 0.1:
            ecarts.append((t, jour["c"], v["cours"], e))
    return ecarts


def main():
    ap = argparse.ArgumentParser(description="Bulletin « Indices » CDG Capital Bourse")
    ap.add_argument("pdf", type=Path, nargs="+",
                    help="bulletin de cotations, et éventuellement la variante DataChart")
    ap.add_argument("--json", type=Path, help="écrit le relevé au format JSON")
    ap.add_argument("--verifier", metavar="AAAA-MM-JJ",
                    help="compare le bulletin à nos chandelles pour cette séance")
    a = ap.parse_args()

    manquants = [f for f in a.pdf if not f.exists()]
    if manquants:
        print(f"❌ introuvable(s) : {', '.join(map(str, manquants))}")
        return 1

    cot, heures = {}, []
    for f in a.pdf:
        cot.update(parse_cotations(f))
        h = date_seance(f)
        if h:
            heures.append(h)
    if not cot:
        print("❌ aucune ligne de cotation reconnue.\n"
              "   La variante DataChart seule ne suffit pas : ajouter le bulletin\n"
              "   de cotations du même jour, qui porte la table clôture → instrument.")
        return 1

    # les séries se lisent dans n'importe lequel des fichiers, une fois la
    # table des clôtures constituée
    ser = {}
    for f in a.pdf:
        for code, vals in parse_series(f, cot).items():
            if len(vals) > len(ser.get(code, ())):
                ser[code] = vals

    cotes = sum(1 for v in cot.values() if v["cours"])
    print(f"{len(cot)} instruments · {cotes} cotés · {len(ser)} séries de clôtures")
    print(f"dernier échange à {max(heures) if heures else '?'} "
          f"(⚠️ le titre du bulletin porte la date de publication, pas celle de la séance)")
    inconnus = [c for c in cot if TICKER_BVC.get(c, c) not in ISIN_MAP]
    if inconnus:
        print(f"hors de notre univers : {' '.join(sorted(inconnus))}")

    if a.json:
        a.json.write_text(json.dumps(
            {"cotations": cot, "series": ser}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"→ {a.json}")

    if a.verifier:
        ecarts = comparer(cot, a.verifier)
        print(f"\nséance {a.verifier} — {len(ecarts)} écart(s) > 0,1% :")
        for t, nous, eux, e in sorted(ecarts, key=lambda x: -abs(x[3])):
            print(f"   {t:6}{COMPANY_NAMES.get(t, '?')[:26]:26}"
                  f"nous={nous:<10} CDG={eux:<10} {e:+.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
