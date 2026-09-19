#!/usr/bin/env python3
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "tests" / "test_serie_et_cache.py"
s = p.read_text(encoding="utf-8")
marker = "def _series_modifiees_dans_cette_livraison() -> set:\n"
if s.count(marker) != 1:
    raise SystemExit(f"marqueur attendu une fois, trouvé {s.count(marker)}")
prefix = s.split(marker, 1)[0]
new_tail = r'''def _series_modifiees_dans_cette_livraison() -> set:
    """Titres dont l'HISTORIQUE DÉJÀ PUBLIÉ a réellement été réécrit.

    Ajouter la séance du jour n'est pas réécrire l'histoire. Remplacer la
    dernière bougie du jour pendant la séance ne l'est pas non plus : à 12h et
    à 15h45, le même jour évolue encore. En revanche, toute différence avant
    cette dernière date quotidienne reste une réécriture historique et doit
    disposer d'une instruction réceptionnée dans le dépôt.
    """
    import subprocess
    import sys as _sys
    from datetime import datetime
    from zoneinfo import ZoneInfo

    _sys.path.insert(0, str(RACINE))
    try:
        from bvc_config import SEANCES_ANNULEES as _annulees
    except ImportError:
        _annulees = {}
    try:
        sortie = subprocess.check_output(
            ["git", "diff", "--name-only", "origin/main", "--", "pipeline/candles"],
            text=True, cwd=RACINE, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return set()

    aujourd_hui = datetime.now(ZoneInfo("Africa/Casablanca")).strftime("%Y-%m-%d")
    reecrits = set()
    for chemin in (l for l in sortie.split() if l.endswith(".json")):
        t = Path(chemin).stem
        try:
            base = json.loads(subprocess.check_output(
                ["git", "show", f"origin/main:{chemin}"],
                text=True, cwd=RACINE, stderr=subprocess.DEVNULL))
            livre = json.loads((RACINE / chemin).read_text(encoding="utf-8"))
        except (subprocess.CalledProcessError, OSError, json.JSONDecodeError):
            reecrits.add(t)
            continue
        if not base:
            continue

        # Une séance juridiquement annulée doit disparaître des deux côtés de
        # la comparaison : son retrait n'est pas une correction historique.
        base = [b for b in base if b["d"] not in _annulees]
        if not base:
            continue

        fin = base[-1]["d"]
        # Si origin/main contient déjà la bougie d'AUJOURD'HUI, elle est encore
        # mutable pendant la séance. Tout ce qui la précède reste immuable.
        if fin == aujourd_hui:
            base_immuable = base[:-1]
            livre_immuable = [b for b in livre if b["d"] < fin]
        else:
            base_immuable = base
            livre_immuable = [b for b in livre if b["d"] <= fin]
        if base_immuable != livre_immuable:
            reecrits.add(t)
    return reecrits


def _candles_touchees_dans_cette_livraison() -> set:
    """Tous les fichiers candles modifiés, append quotidien compris."""
    import subprocess
    try:
        sortie = subprocess.check_output(
            ["git", "diff", "--name-only", "origin/main", "--", "pipeline/candles"],
            text=True, cwd=RACINE, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return set()
    return {Path(x).stem for x in sortie.split() if x.endswith(".json")}


def test_hors_series_corrigees_le_cache_livre_suit_exactement_le_mode_autorise():
    """Le cache livré n'a que deux chemins légitimes.

    1. Une série historique explicitement réceptionnée peut être recalculée en
       complet.
    2. Une bougie quotidienne ajoutée/remplacée peut utiliser --sync-ajouts,
       mais le résultat livré doit être EXACTEMENT celui que ce mode produit à
       partir du cache de origin/main. Les corrections historiques divergentes
       restent donc protégées champ par champ.

    Sans changement de candle, seul le RSI peut encore varier.
    """
    import subprocess
    import recalculer_cache as rc

    try:
        base = json.loads(subprocess.check_output(
            ["git", "show", "origin/main:pipeline/historical_data.json"],
            text=True, cwd=RACINE, stderr=subprocess.DEVNULL))
    except subprocess.CalledProcessError:
        pytest.skip("origin/main absent de ce clone")
    livre = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))

    reecrits = _series_modifiees_dans_cette_livraison()
    autorises_complet = _titres_dont_la_serie_a_change() & reecrits
    univers = len([k for k in base if not k.startswith("_")])
    assert len(reecrits) < univers / 3, (
        f"cette livraison réécrit {len(reecrits)} séries sur {univers} "
        f"— opération de masse : {sorted(reecrits)}")

    candles_touchees = _candles_touchees_dans_cette_livraison()
    moteur = rc._collecteur()
    fautifs = {}

    for t in (k for k in base if not k.startswith("_") and k not in autorises_complet):
        actuel = livre.get(t, {})
        if actuel == base[t]:
            continue

        # Append/remplacement quotidien : le cache doit être celui du mode sûr,
        # pas seulement « ressembler » à un recalcul plausible.
        if t in candles_touchees and t not in reecrits:
            f = RACINE / "pipeline" / "candles" / f"{t}.json"
            if not f.exists():
                fautifs[t] = ["candles_absentes"]
                continue
            serie = json.loads(f.read_text(encoding="utf-8"))
            attendu, rapport = rc._synchroniser_un_ajout(
                t, dict(base[t]), serie, moteur)
            if attendu is None:
                fautifs[t] = ["sync_refusee: " + rapport.get("motif", "?")]
                continue
            champs = sorted(k for k in set(attendu) | set(actuel)
                            if attendu.get(k) != actuel.get(k))
            if champs:
                fautifs[t] = champs
            continue

        # Sans candle quotidienne, l'ancien contrat reste strict : seul RSI.
        champs = {k for k in set(base[t]) | set(actuel)
                  if base[t].get(k) != actuel.get(k)}
        hors_rsi = sorted(champs - {"rsi"})
        if hors_rsi:
            fautifs[t] = hors_rsi

    assert fautifs == {}, (
        "cache modifié hors du chemin autorisé (recalcul réceptionné, "
        f"sync-ajouts exacte ou RSI seul) : {fautifs}")
'''
p.write_text(prefix + new_tail, encoding="utf-8")
print("garde-fou cache livraison mis à jour")
