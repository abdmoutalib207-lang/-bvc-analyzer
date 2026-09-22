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

Un titre explicitement connu de ``ISIN_MAP`` peut ne pas encore avoir de série
locale. Dans ce seul cas, une série est initialisée avec la bougie réellement
observée dans le bulletin. Aucun historique antérieur n'est inventé.
"""
from __future__ import annotations

import argparse
import math
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
CANDLES = ROOT / "pipeline" / "candles"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bvc_config import IDB_TICKER_MAP, ISIN_MAP, seance_annulee, est_suspendu  # noqa: E402
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
    montant_mad = float(ligne.get("volume") or 0)
    quantite = float(ligne.get("qte") or 0)
    if not all(math.isfinite(x) for x in (o,h,l,c,quantite,montant_mad)):
        raise ValueError('OHLCV non fini')
    if not quantite.is_integer():
        raise ValueError('Quantité non entière')
    q = int(quantite)
    if min(o, h, l, c) <= 0:
        raise ValueError(f"OHLC non positif: o={o} h={h} l={l} c={c}")
    if h < max(o, c, l) or l > min(o, c, h):
        raise ValueError(f"OHLC incohérent: o={o} h={h} l={l} c={c}")
    if q <= 0:
        raise ValueError(f"cours coté mais quantité nulle: c={c} q={q}")
    if montant_mad < 0:
        raise ValueError(f"volume monétaire négatif: {montant_mad}")
    # Convention historique du projet : ``v`` = nombre de titres échangés.
    # Le bulletin fournit aussi un montant MAD, utile pour contrôle mais qui ne
    # doit jamais être injecté dans l'OBV ou les indicateurs de volume.
    return {"d": date, "o": o, "h": h, "l": l, "c": c, "v": q}


def traduire_source(doc: dict) -> tuple[dict[str, dict], dict]:
    meta = doc.get("_meta") or {}
    date = str(meta.get("session_date") or "")[:10]
    datetime.strptime(date, '%Y-%m-%d')
    if date > datetime.now(ZoneInfo('Africa/Casablanca')).date().isoformat():
        raise ValueError('Séance future refusée')
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
        if est_suspendu(ticker, date):
            raise ValueError(f'{ticker}: cotation pendant une suspension')
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


def completion(capturee: dict, officielle: dict) -> bool:
    """La bougie du bulletin est-elle la COMPLÉTION de celle qu'on a capturée ?

    Fonction pure : elle compare deux bougies et ne lit rien d'autre.

    ⚠️ POURQUOI CETTE NOTION EXISTE — LA SÉANCE DU 21/09/2026
    ─────────────────────────────────────────────────────────
    Le moteur écrit la bougie du jour dès le premier run et la RAFRAÎCHIT à
    chaque passage suivant. Le 21/09, le dernier run réussi date de 10h44 —
    en pleine séance — et tous ceux d'après la clôture ont échoué. Les bougies
    sont donc restées figées en vol : ouverture juste, extrêmes partiels,
    clôture et volume tronqués.

    Mesuré sur les 60 titres comparables : **l'ouverture n'est JAMAIS en écart,
    le volume l'est TOUJOURS**, et les extrêmes seulement là où la séance a
    débordé après notre dernière capture. Ce n'est pas une source qui en
    contredit une autre, c'est la même séance, inachevée.

    ⚠️ CE QUE LA RÈGLE EXIGE, ET POURQUOI ELLE N'EST PAS UN BLANC-SEING
    ──────────────────────────────────────────────────────────────────
    Une séance ne peut que s'étendre. La bougie officielle doit donc
    ENVELOPPER la nôtre :

        même ouverture  ·  le haut ne recule pas  ·  le bas ne remonte pas
        ·  le volume ne décroît pas

    Si l'une de ces quatre conditions tombe, les deux bougies ne décrivent pas
    la même séance vue à deux instants : elles se contredisent, et
    l'écrasement reste refusé. Sur les 60 titres du 21/09, zéro violation.

    ⚠️ La CLÔTURE a le droit de bouger dans les deux sens — c'est précisément
    ce qu'on vient chercher — MAIS SEULEMENT SI LE VOLUME A CRÛ. Une clôture
    ne se déplace que lorsqu'un échange a lieu, et un échange incrémente le
    volume. Une clôture qui change à volume constant n'est donc pas une séance
    vue plus tard : c'est une contradiction entre deux relevés, et elle reste
    refusée. Cette condition manquait à ma première version ; c'est un test
    déjà présent qui l'a établie, sur le cas `c 378 → 377, v 10 → 10`.
    """
    if not capturee or not officielle:
        return False
    if str(capturee.get("d") or "") != str(officielle.get("d") or ""):
        return False
    try:
        if float(capturee["o"]) != float(officielle["o"]):
            return False
        if float(officielle["h"]) < float(capturee["h"]):
            return False
        if float(officielle["l"]) > float(capturee["l"]):
            return False
        if int(officielle["v"]) < int(capturee["v"]):
            return False
        # ⚠️ Une clôture ne bouge qu'avec un échange, et un échange fait
        # croître le volume. Clôture différente + volume identique =
        # contradiction, pas complétion.
        if (float(officielle["c"]) != float(capturee["c"])
                and int(officielle["v"]) == int(capturee["v"])):
            return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


def importer(source: Path, candles_dir: Path = CANDLES, *, ecrire: bool = False,
             policy: Callable = appliquer_corrections_avant_ecriture) -> dict:
    doc = json.loads(source.read_text(encoding="utf-8"))
    bougies, rapport = traduire_source(doc)
    date = rapport["session_date"]

    # Préparer TOUTES les séries avant la première écriture.
    candidats: dict[str, list] = {}
    deja, ajoutes, series_creees, completees = [], [], [], []
    for ticker, nouvelle in bougies.items():
        f = candles_dir / f"{ticker}.json"
        if f.exists():
            serie = json.loads(f.read_text(encoding="utf-8"))
        else:
            # _ticker_interne() n'admet ici que des titres explicitement connus
            # de notre référentiel. On démarre à la première séance prouvée ;
            # surtout, on ne fabrique aucune séance antérieure.
            if ticker not in ISIN_MAP:
                raise FileNotFoundError(f"série absente pour ticker non référencé {ticker}: {f}")
            serie = []
            series_creees.append(ticker)

        existantes = [b for b in serie if str(b.get("d") or "")[:10] == date]
        if len(existantes) > 1:
            raise ValueError(f"{ticker}: date {date} dupliquée dans la série")
        est_completion = False
        if existantes:
            if existantes[0] == nouvelle:
                deja.append(ticker)
                candidats[ticker] = serie
                continue
            if not completion(existantes[0], nouvelle):
                raise ValueError(
                    f"{ticker}: bougie {date} déjà présente mais différente; "
                    "écrasement automatique refusé")
            # ⚠️ COMPLÉTION, PAS ÉCRASEMENT — voir `completion()`.
            est_completion = True
            serie = [b for b in serie if str(b.get("d") or "")[:10] != date]

        serie_candidate = sorted(serie + [nouvelle], key=lambda b: str(b.get("d") or ""))
        corrigee, garde = policy(ticker, serie_candidate)
        refus = (garde or {}).get("refus") or []
        if refus:
            raise ValueError(f"{ticker}: politique d'écriture refuse la série: {refus}")
        trouvee = next((b for b in corrigee if str(b.get("d") or "")[:10] == date), None)
        if trouvee != nouvelle:
            raise ValueError(f"{ticker}: la politique a altéré/retiré la bougie source {date}")
        candidats[ticker] = corrigee
        (completees if est_completion else ajoutes).append(ticker)

    if ecrire:
        candles_dir.mkdir(parents=True, exist_ok=True)
        a_ecrire = set(ajoutes) | set(completees)
        for ticker, serie in candidats.items():
            if ticker not in a_ecrire:
                continue
            cible = candles_dir / f"{ticker}.json"
            cible.write_text(
                json.dumps(serie, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

    rapport.update({
        "ecriture": bool(ecrire),
        "ajoutes": sorted(ajoutes),
        "series_creees": sorted(series_creees),
        "deja_presents_identiques": sorted(deja),
        "completees": sorted(completees),
        "n_ajoutes": len(ajoutes),
        "n_completees": len(completees),
        "_lecture_completees":
            "bougies capturées EN SÉANCE puis complétées par la clôture du "
            "bulletin. Chacune a dû ENVELOPPER la capture — même ouverture, "
            "haut qui ne recule pas, bas qui ne remonte pas, volume qui ne "
            "décroît pas. Toute contradiction a été refusée.",
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
