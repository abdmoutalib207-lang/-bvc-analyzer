"""Prépare uniquement des chandelles OHLCV réellement observées et datées."""
import json
from math import isfinite
from pathlib import Path

from bvc_config import est_suspendu, seance_annulee
from pipeline.candle_write_policy import appliquer_corrections_avant_ecriture


def preparer(live_prices, seance, aujourd_hui, dossier, tickers):
    """Sans écriture ; une ancienne séance déjà enregistrée reste immuable."""
    if not seance or seance_annulee(seance) or seance > aujourd_hui:
        return {}
    sorties = {}
    for sym, q in live_prices.items():
        if sym not in tickers or q.get('src') not in ('cdg', 'bmce'):
            continue
        if q.get('asof') != seance or est_suspendu(sym, seance):
            continue
        try:
            o, h, l, c, v = (float(q[k]) for k in ('open', 'high', 'low', 'price', 'vol'))
        except (KeyError, TypeError, ValueError):
            continue
        if not all(isfinite(x) for x in (o,h,l,c,v)) or v <= 0 or not v.is_integer():
            continue
        if not (0 < l <= min(o,c) <= max(o,c) <= h):
            continue
        p = Path(dossier) / f'{sym}.json'
        serie = json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
        derniere = serie[-1] if serie else None
        if derniere and (derniere['d'] > seance or
                         (seance < aujourd_hui and derniere['d'] == seance)):
            continue
        rafraichir = derniere and derniere['d'] == seance
        if rafraichir and derniere.get('v', 0) > v:
            continue
        bougie = dict(d=seance, o=o, h=h, l=l, c=c, v=int(v))
        if rafraichir:
            bougie['h'] = max(h, derniere['h'])
            bougie['l'] = min(l, derniere['l'])
        candidate = [b for b in serie if b['d'] != seance] + [bougie]
        candidate, rapport = appliquer_corrections_avant_ecriture(sym, candidate)
        if rapport.get('refus'):
            raise ValueError(f'{sym}: cotation refusée par la politique commune')
        if candidate != serie:
            sorties[sym] = candidate
    return sorties
