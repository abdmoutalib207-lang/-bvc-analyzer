from pathlib import Path

p = Path('pipeline/recalculer_cache.py')
s = p.read_text(encoding='utf-8')
old = '''def _fusion_candles_cache(candles_cache: list, candles_calculees: list,
                           depuis: str) -> list:
    """Préserve le passé du cache et remplace/ajoute seulement sa queue récente."""
    base = [dict(b) for b in (candles_cache or [])
            if str(b.get("d") or "")[:10] < depuis]
    queue = [dict(b) for b in (candles_calculees or [])
             if str(b.get("d") or "")[:10] >= depuis]
    par_date = {str(b.get("d") or "")[:10]: b for b in base + queue
                if b.get("d")}
    return [par_date[d] for d in sorted(par_date)][-250:]
'''
new = '''def _fusion_candles_cache(candles_cache: list, candles_calculees: list,
                           pivot: str, remplacer_pivot: bool) -> list:
    """Préserve le passé corrigé du cache et ne fusionne que la queue utile.

    Pour un APPEND (nouvelle séance > pivot), la dernière bougie déjà livrée
    fait partie du passé réceptionné et doit être conservée telle quelle : le
    brut peut encore contenir une anomalie que le cache avait corrigée.

    Pour un REMPLACEMENT de la dernière séance (intraday), le pivot lui-même
    est au contraire remplacé par le nouveau calcul.
    """
    if remplacer_pivot:
        base = [dict(b) for b in (candles_cache or [])
                if str(b.get("d") or "")[:10] < pivot]
        queue = [dict(b) for b in (candles_calculees or [])
                 if str(b.get("d") or "")[:10] >= pivot]
    else:
        base = [dict(b) for b in (candles_cache or [])
                if str(b.get("d") or "")[:10] <= pivot]
        queue = [dict(b) for b in (candles_calculees or [])
                 if str(b.get("d") or "")[:10] > pivot]
    par_date = {str(b.get("d") or "")[:10]: b for b in base + queue
                if b.get("d")}
    return [par_date[d] for d in sorted(par_date)][-250:]
'''
if old not in s:
    raise SystemExit('bloc _fusion_candles_cache introuvable ou déjà modifié')
s = s.replace(old, new, 1)
old2 = '''    entree_nouvelle["candles"] = _fusion_candles_cache(
        entree.get("candles") or [], calc_apres.get("candles") or [], ancienne_date)
'''
new2 = '''    entree_nouvelle["candles"] = _fusion_candles_cache(
        entree.get("candles") or [], calc_apres.get("candles") or [], ancienne_date,
        remplacer_pivot=(derniere_date == ancienne_date))
'''
if old2 not in s:
    raise SystemExit('appel _fusion_candles_cache introuvable ou déjà modifié')
s = s.replace(old2, new2, 1)
p.write_text(s, encoding='utf-8')
print('recalculer_cache.py patché')
