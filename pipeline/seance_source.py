"""Dernière séance observée chez CDG, indépendante des fichiers locaux."""
import json
from collections import Counter
from datetime import datetime
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from bvc_config import seance_annulee


def lire_date_cdg(lignes, aujourd_hui=None):
    aujourd_hui = aujourd_hui or datetime.now(ZoneInfo('Africa/Casablanca')).date().isoformat()
    dates = Counter()
    for r in lignes:
        try:
            d = datetime.strptime(str(r.get('DateDernierCours', ''))[:10], '%d/%m/%Y').date().isoformat()
            cote = float(r.get('Cours') or 0) > 0 and float(r.get('QteEchangee') or 0) > 0
        except (ValueError, TypeError):
            continue
        if cote and d <= aujourd_hui and not seance_annulee(d):
            dates[d] += 1
    recevables = [d for d, n in dates.items() if n >= 20]
    if not recevables:
        raise ValueError('Pas de séance CDG datée sur au moins 20 titres')
    return max(recevables)


def derniere_seance_source():
    params = [('Lang_', 'S', 'fr'), ('Espace_', 'I', '1'), ('IdPartener_', 'I', '1'),
              ('TypeStocks_', 'S', '1'), ('TypeCotation_', 'S', '0')]
    body = {'ACTIONS': [{'ACTION': {'NAME': 'MARKET-RESUME', 'TYPE': 'SELECT', 'VALUE': 'MARKET-RESUME'},
                         'PARAMS': [dict(NAME=n, TYPE=t, VALUE=v) for n,t,v in params]}]}
    req = Request('https://www.cdgcapitalbourse.ma/api/', data=json.dumps(body).encode(),
                  headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0',
                           'Referer': 'https://www.cdgcapitalbourse.ma/Bourse/market'})
    with urlopen(req, timeout=30) as response:
        bloc = json.load(response)[0]['MARKET-RESUME']
    if not bloc.get('Valid'):
        raise ValueError('Réponse CDG invalide')
    lignes = bloc['Data']
    if lignes and isinstance(lignes[0], list):
        lignes = lignes[0]
    return lire_date_cdg(lignes)
