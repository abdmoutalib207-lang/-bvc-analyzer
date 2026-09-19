#!/usr/bin/env python3
"""Importe une séance de clôture CDG dans les chandelles BVC Analyzer.

Le relevé source utilise les codes officiels BVC/CDG. Ils sont TOUJOURS
traduits via ``IDB_TICKER_MAP`` avant écriture (SID=Sonasid→SNA interne,
SNA=Stokvis→STK interne). Les lignes à cours nul signifient « aucun échange »
et ne créent pas de bougie artificielle.

L'import est transactionnel : toutes les lignes sont validées et soumises à la
politique commune de corrections avant la première écriture. Une bougie déjà
présente à la même date doit être strictement identique, sinon l'import refuse
au lieu d'écraser silencieusement une autre source.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
CANDLES = ROOT / "pipeline" / "candles"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bvc_config import IDB_TICKER_MAP, ISIN_MAP, seance_annulee  # noqa: E402
from pipeline.candle_write_policy import appliquer_corrections_avant_ecriture  # noqa: E402

BVC_VERS_INTERNE = {code: ticker for ticker, code in IDB_TICKER_MAP.items()}


def _ticker_interne(code: str) -> str | None:
    t = BVC_VERS_INTERNE.get(code)
    if t:
        return t
    # Identité admise seulement si le code fait explicitement partie de notre
    # référentiel interne. On ne déduit jamais SNA/SID par égalité de chaîne.
    return code if code in ISIN_MAP else None


def _bougie(date: str, ligne: dict) -> dict:
    o = float(ligne["ouverture"])
    h = float(ligne["haut"])
    l = float(ligne["bas"])
    c = float(ligne["cours"])
    v = float(ligne.get("volume") or 0)
    q = int(ligne.get("qte") or 0)
    if min(o, h, l, c) <= 0:
        raise ValueError(f"OHLC non positif: o={o} h={h} l={l} c={c}")
    if h < max(o, c, l) or l > min(o, c, h):
        raise ValueError(f"OHLC incohérent: o={o} h={h} l={l} c={c}")
    if q <= 0:
        raise ValueError(f"cours coté mais quantité nulle: c={c} q={q}")
    if v < 0:
        raise ValueError(f"volume monétaire négatif: {v}")
    # Dans ce projet, ``v`` est le volume monétaire MAD, pas le nombre de titres.
    return {"d": date, "o": o, "h": h, "l": l, "c": c, "v": v}


def traduire_source(doc: dict) -> tuple[dict[str, dict], dict]:
    meta = doc.get("_meta") or {}
    date = str(meta.get("session_date") or "")[:10]
    if len(date) != 10:
        raise ValueError("session_date absente ou invalide")
    if seance_annulee(date):
        raise ValueError(f"la séance {date} est déclarée annulée: import refusé")

    cotations = doc.get("cotations") or {}
    if not isinstance(cotations, dict) or not cotations:
        raise ValueError("aucune cotation dans le relevé")

    actives: dict[str, dict] = {}
    sans_echange, hors_univers = [], []
    collision = {}
    for code, ligne in sorted(cotations.items()):
        cours = float((ligne or {}).get("cours") or 0)
        if cours <= 0:
            sans_echange.append(code)
            continue
        ticker = _ticker_interne(code)
        if not ticker:
            hors_univers.append(code)
            continue
        if ticker in actives:
            collision.setdefault(ticker, []).append(code)
            continue
        actives[ticker] = _bougie(date, ligne)

    if hors_univers:
        raise ValueError("codes cotés hors univers: " + " ".join(hors_univers))
    if collision:
        raise ValueError("codes sources en collision après traduction: " + repr(collision))

    rapport = {
        "session_date": date,
        "source": meta.get("source"),
        "source_document": meta.get("source_document"),
        "lignes_source": len(cotations),
        "bougies_cotees": len(actives),
        "sans_echange": sans_echange,
        "hors_univers": hors_univers,
        "tickers": sorted(actives),
    }
    return actives, rapport


def importer(source: Path, candles_dir: Path = CANDLES, *, ecrire: bool = False,
             policy: Callable = appliquer_corrections_avant_ecriture) -> dict:
    doc = json.loads(source.read_text(encoding="utf-8"))
    bougies, rapport = traduire_source(doc)
    date = rapport["session_date"]

    # Préparer TOUTES les séries avant la première écriture.
    candidats: dict[str, list] = {}
    deja, ajoutes = [], []
    for ticker, nouvelle in bougies.items():
        f = candles_dir / f"{ticker}.json"
        if not f.exists():
            raise FileNotFoundError(f"série absente pour {ticker}: {f}")
        serie = json.loads(f.read_text(encoding="utf-8"))
        existantes = [b for b in serie if str(b.get("d") or "")[:10] == date]
        if len(existantes) > 1:
            raise ValueError(f"{ticker}: date {date} dupliquée dans la série")
        if existantes:
            if existantes[0] != nouvelle:
                raise ValueError(
                    f"{ticker}: bougie {date} déjà présente mais différente; "
                    "écrasement automatique refusé")
            deja.append(ticker)
            candidats[ticker] = serie
            continue

        serie_candidate = sorted(serie + [nouvelle], key=lambda b: str(b.get("d") or ""))
        corrigee, garde = policy(ticker, serie_candidate)
        refus = (garde or {}).get("refus") or []
        if refus:
            raise ValueError(f"{ticker}: politique d'écriture refuse la série: {refus}")
        trouvee = next((b for b in corrigee if str(b.get("d") or "")[:10] == date), None)
        if trouvee != nouvelle:
            raise ValueError(f"{ticker}: la politique a altéré/retiré la bougie source {date}")
        candidats[ticker] = corrigee
        ajoutes.append(ticker)

    if ecrire:
        candles_dir.mkdir(parents=True, exist_ok=True)
        for ticker, serie in candidats.items():
            if ticker not in ajoutes:
                continue
            cible = candles_dir / f"{ticker}.json"
            cible.write_text(
                json.dumps(serie, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

    rapport.update({
        "ecriture": bool(ecrire),
        "ajoutes": sorted(ajoutes),
        "deja_presents_identiques": sorted(deja),
        "n_ajoutes": len(ajoutes),
    })
    return rapport


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path)
    ap.add_argument("--ecrire", action="store_true")
    ap.add_argument("--rapport", type=Path)
    a = ap.parse_args()
    rapport = importer(a.source, ecrire=a.ecrire)
    texte = json.dumps(rapport, ensure_ascii=False, indent=2)
    print(texte)
    if a.rapport:
        a.rapport.write_text(texte + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
