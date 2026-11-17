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
        if derniere and derniere['d'] > seance:
            continue
        # ⚠️ UNE SÉANCE ÉCHUE NE SE RÉÉCRIT PAS — sauf pour COMPLÉTER son
        # volume. Le 05/10/2026, CDG a servi jusqu'à 16h55 au moins des
        # quantités arrêtées avant les derniers échanges du fixing (HPS 5 851
        # titres au lieu de 7 818), puis les bonnes à 17h15. Sans run entre
        # les deux et minuit, la bougie restait fausse à jamais. On accepte
        # donc, le lendemain, la MÊME séance si sa clôture est identique et
        # son volume plus grand : rien d'autre ne peut passer par là.
        # Seul le VOLUME change (ouverture et extrêmes stockés conservés), et
        # seulement depuis CDG : BMCE pourrait compter autrement.
        completer = (derniere and seance < aujourd_hui and derniere['d'] == seance)
        if completer and not (q.get('src') == 'cdg' and v > derniere.get('v', 0)):
            continue
        # ⚠️ 17/11/2026 — ET SI LA CLÔTURE A CHANGÉ, ELLE AUSSI. Le 16/11, les
        # runs du soir ont tous été refusés par la garde (titre hors registre,
        # voir `marche_history.annoter_hors_registre`) : la bougie du 16/11
        # est restée celle du run de 14h56 (IAM 89,40 sur 18 002 titres, au
        # lieu de 90,00 sur 64 115). Passé minuit, la règle « clôture
        # identique » la refusait pour toujours, et 37 titres sont tombés en
        # « cours en désaccord avec la dernière clôture » — Score BVC non
        # calculable. Le garde-fou qui compte est le VOLUME, qui ne recule
        # jamais dans une séance : une quantité CDG STRICTEMENT plus grande
        # décrit un état plus avancé de la MÊME séance. Une clôture définitive
        # ne peut plus être dépassée ; elle n'est donc jamais réécrite.
        completer_volume = completer and c == derniere['c']
        rafraichir = derniere and derniere['d'] == seance
        if rafraichir and derniere.get('v', 0) > v:
            continue
        bougie = dict(d=seance, o=o, h=h, l=l, c=c, v=int(v))
        if completer_volume:
            bougie = {**derniere, 'v': int(v)}
        elif rafraichir:
            bougie['h'] = max(h, derniere['h'])
            bougie['l'] = min(l, derniere['l'])
        candidate = [b for b in serie if b['d'] != seance] + [bougie]
        candidate, rapport = appliquer_corrections_avant_ecriture(sym, candidate)
        if rapport.get('refus'):
            if completer:
                # Une correction réceptionnée fixe cette séance : la
                # complétion s'efface devant elle, sans bloquer la publication.
                continue
            raise ValueError(f'{sym}: cotation refusée par la politique commune')
        if candidate != serie:
            sorties[sym] = candidate
    return sorties
