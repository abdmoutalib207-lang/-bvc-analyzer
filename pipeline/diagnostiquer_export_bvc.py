#!/usr/bin/env python3
"""Compare nos chandelles à un export « Cours » de casablanca-bourse.com.

⚠️ CE QUE CET OUTIL A SERVI À DÉCOUVRIR, ET QUI N'ÉTAIT PAS CE QU'ON CHERCHAIT
─────────────────────────────────────────────────────────────────────────────
Il a été écrit pour mesurer un défaut connu : le volume stocké en DIRHAMS au
lieu d'un nombre de titres. L'export porte les deux colonnes — « Volume (MAD) »
et « Titres Échangés » — et un chargeur qui retient « la première colonne
contenant vol » prend le montant.

Il en a trouvé deux autres, invisibles depuis le terminal :

  2. **le cours recopié dans le volume** les séances SANS ÉCHANGE. L'export
     écrit « - » ; nous portons un nombre qui est l'ordre de grandeur du COURS
     (CDM : v=700 pour un titre qui cote 700). Un titre qui n'a pas échangé
     apparaît donc comme ayant échangé ;
  3. **des clôtures fausses** sur une fenêtre précise — 534 séances sur les
     27 titres, concentrées du 18/06 au 06/08/2026, dont une part vaut
     exactement la clôture de la VEILLE.

Le troisième n'est pas un défaut de volume : c'est un défaut de PRIX, et il
tombe sous R1. Il a été trouvé parce qu'on a comparé la colonne d'à côté.

⚠️ L'OUTIL NE CORRIGE RIEN, ET C'EST VOULU.
Il mesure et il nomme. La réparation passe par la réception documentée d'un
historique (`datasets/historiques_importes/`), qui porte la source, l'empreinte
du fichier reçu et la preuve d'identité. Un outil qui diagnostiquerait ET
écrirait ferait disparaître cette trace.

⚠️ L'IDENTITÉ SE LIT DANS LE FICHIER, JAMAIS DANS SON NOM.
Le code de l'export est celui de l'OPÉRATEUR : `TGC` est notre TGCC, `NKL`
notre ENK, `SNA` est Stokvis et non Sonasid. On résout par `IDB_TICKER_MAP`
inversé sur le code LU dans la colonne `Ticker`, et on vérifie que le nom
d'instrument concorde. Un nom de fichier n'est pas une preuve d'identité.

Usage :
    python3 pipeline/diagnostiquer_export_bvc.py <export.csv> [...]
    python3 pipeline/diagnostiquer_export_bvc.py --detail <export.csv>
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from bvc_config import IDB_TICKER_MAP  # noqa: E402

CANDLES = RACINE / "pipeline" / "candles"

# Tolérance relative sur un cours. Deux décimales publiées, des arrondis de
# part et d'autre : 0,1 % laisse passer le bruit de représentation et rien
# d'autre — l'écart le plus faible réellement observé vaut 0,3 %.
TOLERANCE_COURS = 0.001


def nombre(brut: str | None) -> float | None:
    """Un nombre de l'export, ou None quand la colonne dit « rien ».

    ⚠️ « - » n'est pas zéro et ne doit pas le devenir ici : sur la colonne des
    titres échangés il signifie « pas d'échange », ce qui EST une information —
    c'est elle qui démasque le défaut n°2. La confondre avec 0 par commodité
    reviendrait à effacer la question qu'on est venu poser.
    """
    texte = (brut or "").strip().replace(" ", "").replace(" ", "")
    if texte in ("", "-", "—"):
        return None
    try:
        return float(texte)
    except ValueError:
        return None


def lire_export(chemin: Path) -> tuple[str, str, dict]:
    """(code opérateur, nom d'instrument, {AAAA-MM-JJ: ligne}).

    ⚠️ Le fichier est servi avec un BOM : sans `utf-8-sig`, la première
    en-tête devient « ﻿Séance » et la colonne des dates est introuvable.
    """
    rows = list(csv.DictReader(
        io.StringIO(chemin.read_text(encoding="utf-8-sig")), delimiter=";"))
    if not rows:
        raise ValueError(f"{chemin.name} : export vide")
    codes = {r["Ticker"].strip() for r in rows}
    if len(codes) != 1:
        raise ValueError(f"{chemin.name} : {len(codes)} codes distincts {codes}")
    par_date = {}
    for r in rows:
        jour, mois, an = r["Séance"].split("/")
        par_date[f"{an}-{mois}-{jour}"] = r
    return codes.pop(), rows[0]["Instrument"].strip(), par_date


def resoudre(code_operateur: str) -> str | None:
    """Notre ticker, à partir du code lu DANS le fichier.

    `IDB_TICKER_MAP` va de notre ticker vers celui de l'opérateur ; on
    l'inverse. Quand le code n'y figure pas, il peut être identique au nôtre —
    on ne l'accepte alors que si la série existe chez nous, faute de quoi on
    refuse plutôt que de deviner.
    """
    inverse = {v: k for k, v in IDB_TICKER_MAP.items()}
    if code_operateur in inverse:
        return inverse[code_operateur]
    if (CANDLES / f"{code_operateur}.json").exists():
        return code_operateur
    return None


def nos_chandelles(ticker: str) -> list[dict]:
    f = CANDLES / f"{ticker}.json"
    if not f.exists():
        return []
    doc = json.loads(f.read_text(encoding="utf-8"))
    return doc if isinstance(doc, list) else (doc.get("candles") or [])


def diagnostiquer(chemin: Path) -> dict:
    """Le relevé d'un titre : ce qui concorde, et chaque défaut nommé."""
    code, instrument, officiel = lire_export(chemin)
    ticker = resoudre(code)
    if ticker is None:
        return {"fichier": chemin.name, "code_operateur": code,
                "instrument": instrument, "refus": "identité non résolue"}

    dates = sorted(officiel)
    veille = {d: (dates[i - 1] if i else None) for i, d in enumerate(dates)}
    candles = nos_chandelles(ticker)
    nos_dates = {b["d"] for b in candles}

    r = {"fichier": chemin.name, "ticker": ticker, "code_operateur": code,
         "instrument": instrument, "seances_export": len(officiel),
         "nos_seances": len(candles),
         "conformes": 0, "volume_en_dirhams": [], "volume_vaut_le_cours": [],
         "cloture_fausse": [], "seances_absentes": sorted(set(officiel) - nos_dates),
         "hors_periode_export": len(nos_dates - set(officiel))}

    for b in candles:
        o = officiel.get(b["d"])
        if not o:
            continue
        titres = nombre(o["Titres Échangés"])
        dirhams = nombre(o["Volume (MAD)"])
        cours = nombre(o["Dernier Cours"])
        v = nombre(str(b.get("v")))
        juste = True

        if cours is not None and \
                abs(float(b["c"]) - cours) / max(cours, 1e-9) > TOLERANCE_COURS:
            juste = False
            p = veille.get(b["d"])
            cours_veille = nombre(officiel[p]["Dernier Cours"]) if p else None
            recul = (cours_veille is not None and
                     abs(float(b["c"]) - cours_veille) / max(cours_veille, 1e-9)
                     <= TOLERANCE_COURS)
            r["cloture_fausse"].append(
                {"d": b["d"], "notre": b["c"], "officiel": cours,
                 "est_la_cloture_de_la_veille": recul})

        if titres is None:
            # L'export ne cote pas d'échange ce jour-là.
            if v:
                juste = False
                r["volume_vaut_le_cours"].append(
                    {"d": b["d"], "notre_v": v, "notre_cours": b["c"]})
        elif v is not None and abs(v - titres) > 1:
            if dirhams and abs(v - dirhams) / max(dirhams, 1) < 0.01:
                juste = False
                r["volume_en_dirhams"].append(
                    {"d": b["d"], "notre_v": v, "titres": titres,
                     "dirhams": dirhams})
            else:
                juste = False
                r.setdefault("volume_inexplique", []).append(
                    {"d": b["d"], "notre_v": v, "titres": titres})
        if juste:
            r["conformes"] += 1
    return r


def _ligne(r: dict) -> str:
    if r.get("refus"):
        return f"{'?':6} {r['code_operateur']:5} {r['instrument'][:24]:24} {r['refus']}"
    return (f"{r['ticker']:6} {r['code_operateur']:5} {r['instrument'][:24]:24} "
            f"{r['conformes']:6} {len(r['volume_en_dirhams']):8} "
            f"{len(r['volume_vaut_le_cours']):9} "
            f"{len(r.get('volume_inexplique', [])):8} "
            f"{len(r['cloture_fausse']):8} {len(r['seances_absentes']):7}")


def main(argv: list[str]) -> int:
    detail = "--detail" in argv
    fichiers = [Path(a) for a in argv if not a.startswith("--")]
    if not fichiers:
        print(__doc__)
        return 2
    releves = [diagnostiquer(f) for f in sorted(fichiers)]
    if detail:
        print(json.dumps(releves, ensure_ascii=False, indent=2))
        return 0
    print(f"{'tk':6} {'code':5} {'instrument':24} {'justes':>6} {'vol=MAD':>8} "
          f"{'vol=cours':>9} {'vol=?':>8} {'clôture':>8} {'absent':>7}")
    for r in releves:
        print(_ligne(r))
    exploitables = [r for r in releves if not r.get("refus")]
    print(f"\n{len(exploitables)}/{len(releves)} titres résolus — "
          f"{sum(len(r['volume_en_dirhams']) for r in exploitables)} volumes en "
          f"dirhams, "
          f"{sum(len(r['volume_vaut_le_cours']) for r in exploitables)} volumes "
          f"valant le cours, "
          f"{sum(len(r['cloture_fausse']) for r in exploitables)} clôtures "
          f"fausses, "
          f"{sum(len(r['seances_absentes']) for r in exploitables)} séances "
          f"absentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
