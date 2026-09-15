#!/usr/bin/env python3
"""Le moteur ENTIER rejoué hors réseau, avant fusion — pour un titre corrigé.

⚠️ D'OÙ VIENT CETTE MÉTHODE
───────────────────────────
Elle est reprise de `pipeline/verifier_candidat_msa.py`, écrit pour le lot MSA.
Ce programme-ci la généralise à n'importe quel titre portant un fichier dans
`datasets/corrections_acceptees/`, pour qu'elle serve à chaque lot au lieu d'un
seul.

⚠️ CE QU'ELLE APPORTE, ET QUE MA MÉTHODE N'AVAIT PAS
────────────────────────────────────────────────────
Jusqu'ici je recalculais le cache du titre corrigé, je lançais la suite, et je
rejouais le moteur EN LIGNE. Trois faiblesses :

  · la comparaison portait sur le cache, pas sur ce que le moteur REND ;
  · rien ne prouvait que les 79 autres titres étaient intacts À LA SORTIE ;
  · le réseau rendait le contrôle non reproductible — deux exécutions à cinq
    minutes d'écart ne donnent pas le même fichier.

Ici, le moteur tourne deux fois sur le MÊME instant figé, dans un bac jetable,
SANS réseau, et l'on compare les deux sorties titre par titre et champ par
champ.

    B  la série SANS les corrections, cache recalculé dessus
    A  la série AVEC les corrections, cache recalculé dessus

⚠️ B est reconstruit en RÉAPPLIQUANT les états `remplace` du lot : c'est
exactement ce que le dépôt portait avant. On ne compare pas à un souvenir.

CE QUE LE CONTRÔLE EXIGE
────────────────────────
  1. les 80 titres sont là, des deux côtés ;
  2. AUCUN autre titre que celui corrigé ne bouge, sur AUCUN champ ;
  3. aucun appel réseau n'a eu lieu — vérifié, pas supposé : un repli qui
     rattraperait un appel en silence ferait passer le contrôle pour bon ;
  4. le dry-run n'a rien écrit dans le bac.

⚠️ CE QU'ELLE N'ÉTABLIT PAS
Les cotations sont reconstituées depuis le `data.json` publié, pas rejouées
depuis les réponses brutes des fournisseurs. C'est un contrôle d'INTÉGRATION
hors réseau, pas une preuve que la collecte du jour était juste, ni qu'un run
GitHub Actions se comportera à l'identique.

    python pipeline/verifier_correction.py SOT
    python pipeline/verifier_correction.py HPS --instant 2026-09-15T21:00:00+01:00
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))

CHAMPS = ("o", "h", "l", "c", "v")


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def serie_sans_corrections(ticker: str, serie: list) -> list:
    """L'état d'AVANT, reconstruit depuis le lot — pas depuis un souvenir.

    ⚠️ Chaque ligne du lot porte `remplace`. Les réappliquer redonne exactement
    ce que le dépôt contenait, ce qui rend la comparaison honnête : si le lot
    décrivait mal l'état antérieur, cette reconstruction ne retomberait pas sur
    lui et la couche refuserait de le recorriger.
    """
    from corrections_acceptees import charger
    doc = charger(ticker)
    if doc is None:
        raise SystemExit(f"{ticker} : aucune correction réceptionnée")
    par_date = {l["d"]: l for l in doc["lignes"]}
    out = []
    for b in serie:
        l = par_date.get(b.get("d"))
        if l is None:
            out.append(dict(b))
            continue
        etat = {k: b.get(k) for k in CHAMPS}
        if etat != l["corrige"]:
            raise SystemExit(
                f"{ticker} {b['d']} : la série publiée ne porte pas la correction "
                f"({etat} au lieu de {l['corrige']}) — vérifier avant de conclure")
        out.append({**b, **l["remplace"]})
    return out, doc


def _indicateurs(serie: list) -> dict:
    """Les vingt champs du cache, calculés par le producteur du cache."""
    import pandas as pd
    sys.argv = ["collect_history_bvcscrap.py"]
    spec = importlib.util.spec_from_file_location(
        "col_verif", RACINE / "pipeline" / "collect_history_bvcscrap.py")
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    df = pd.DataFrame([{"date": pd.Timestamp(b["d"]), "open": b["o"], "high": b["h"],
                        "low": b["l"], "close": b["c"], "volume": b.get("v", 0)}
                       for b in serie])
    return m.compute_indicators(df)


def executer(ticker: str, serie: list, entree_cache: dict, instant: str) -> dict:
    """Un run complet du moteur, dans un bac jetable, sans réseau."""
    import pandas as pd
    import requests

    fige = datetime.fromisoformat(instant)
    if fige.tzinfo is None:
        raise ValueError("l'instant doit porter son fuseau horaire")

    class Horloge(datetime):
        @classmethod
        def now(cls, tz=None):
            return (fige.astimezone(tz) if tz
                    else fige.astimezone(timezone.utc).replace(tzinfo=None))

    publie = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    cotations = {r["symbol"]: {"price": r["price"], "chg": r["chg"], "vol": r["vol"],
                               "open": r["open"], "cap": r["cap"],
                               "asof": r["_meta"]["prix_asof"], "src": "idb"}
                 for r in publie["tickers"]}
    cdg = {r["symbol"]: copy.deepcopy(cotations[r["symbol"]]) for r in publie["tickers"]
           if r["_meta"]["source_prix"] == "cdg"}
    masi = {"value": publie["masi"]["value"], "chg": publie["masi"]["change_pct"],
            "asof": publie["masi"]["asof"], "stale": publie["masi"]["stale"]}

    with tempfile.TemporaryDirectory(prefix="verif-moteur-") as tmp:
        bac = Path(tmp)
        (bac / "pipeline" / "candles").mkdir(parents=True)
        for motif in ("*.json", "pipeline/*.json", "pipeline/candles/*.json"):
            for src in RACINE.glob(motif):
                shutil.copyfile(src, bac / src.relative_to(RACINE))
        cache = json.loads((bac / "pipeline/historical_data.json").read_text())
        cache[ticker] = copy.deepcopy(entree_cache)
        (bac / "pipeline/historical_data.json").write_text(
            json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        (bac / f"pipeline/candles/{ticker}.json").write_text(
            json.dumps(serie, ensure_ascii=False), encoding="utf-8")
        avant = {str(p.relative_to(bac)): _sha(p) for p in bac.rglob("*.json")}

        with ExitStack() as pile:
            # ⚠️ Le réseau est INTERDIT, et son absence est VÉRIFIÉE. Un repli
            # qui rattraperait un appel en silence ferait passer le contrôle
            # pour bon alors qu'il aurait mesuré autre chose.
            http = pile.enter_context(patch.object(
                requests.sessions.Session, "request",
                side_effect=AssertionError("réseau interdit")))
            sock = pile.enter_context(patch(
                "socket.create_connection",
                side_effect=AssertionError("réseau interdit")))
            spec = importlib.util.spec_from_file_location(
                "ud_verif", RACINE / "update_data.py")
            ud = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ud)
            ud.__file__ = str(bac / "update_data.py")
            ud.OUTPUT = bac / "data.json"
            ud.IDB_ASOF = max(q["asof"] for q in cotations.values())
            ud._cdg_lignes = []
            for nom, valeur in (
                    ("datetime", Horloge),
                    ("fetch_all_idb", lambda: copy.deepcopy(cotations)),
                    ("fetch_all_cdg", lambda: copy.deepcopy(cdg)),
                    ("fetch_all_bmce", lambda *_: {}),
                    ("fetch_masi", lambda: copy.deepcopy(masi)),
                    ("fetch_history", lambda *a, **k: pd.DataFrame()),
                    ("fetch_med24_quote", lambda *_: None)):
                pile.enter_context(patch.object(ud, nom, valeur))
            pile.enter_context(patch.object(ud.time, "sleep", lambda *_: None))
            with redirect_stdout(io.StringIO()):
                sortie = ud.run(dry_run=True, push=False)
            http.assert_not_called()
            sock.assert_not_called()

        apres = {str(p.relative_to(bac)): _sha(p) for p in bac.rglob("*.json")}
        if avant != apres:
            raise AssertionError("le dry-run a écrit dans le bac")
        return sortie


def verifier(ticker: str, instant: str) -> dict:
    serie_a = json.loads((RACINE / "pipeline" / "candles" / f"{ticker}.json")
                         .read_text(encoding="utf-8"))
    serie_b, doc = serie_sans_corrections(ticker, serie_a)

    A = executer(ticker, serie_a, _indicateurs(serie_a), instant)
    B = executer(ticker, serie_b, _indicateurs(serie_b), instant)
    ia = {r["symbol"]: r for r in A["tickers"]}
    ib = {r["symbol"]: r for r in B["tickers"]}

    if set(ia) != set(ib):
        raise AssertionError("l'univers des titres diffère entre les deux runs")
    autres = sorted(t for t in ia if t != ticker and ia[t] != ib[t])
    if autres:
        detail = {t: sorted(k for k in set(ia[t]) | set(ib[t])
                            if ia[t].get(k) != ib[t].get(k)) for t in autres[:5]}
        raise AssertionError(
            f"{len(autres)} autre(s) titre(s) modifié(s) par ce lot : {detail}")

    champs = sorted(k for k in set(ia[ticker]) | set(ib[ticker])
                    if ia[ticker].get(k) != ib[ticker].get(k))
    return {
        "_quoi": f"moteur entier rejoué hors réseau, {ticker}",
        "_methode": "reprise de pipeline/verifier_candidat_msa.py (lot MSA), "
                    "généralisée à tout titre corrigé",
        "instant_fige": instant,
        "titres": len(ia),
        "seances_corrigees": len(doc["lignes"]),
        "autres_titres_modifies": 0,
        "champs_deplaces_sur_le_titre": champs,
        "avant_apres": {k: [ib[ticker].get(k), ia[ticker].get(k)] for k in champs},
        "_ce_qui_n_est_pas_etabli":
            "⚠️ Les cotations sont reconstituées depuis le data.json publié, "
            "pas rejouées depuis les réponses brutes des fournisseurs. Contrôle "
            "d'INTÉGRATION hors réseau — ni une preuve que la collecte du jour "
            "était juste, ni qu'un run GitHub Actions se comportera à "
            "l'identique.",
        "_garanties": [
            "aucun appel réseau — vérifié, pas supposé",
            "le dry-run n'a rien écrit dans le bac",
            "les deux runs partagent le même instant figé",
            "l'état d'avant est reconstruit depuis `remplace`, pas depuis un "
            "souvenir",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--instant", default=None,
                    help="horodatage figé, ISO avec fuseau (défaut : maintenant)")
    a = ap.parse_args()
    instant = a.instant or datetime.now().astimezone().replace(
        microsecond=0).isoformat()
    for t in a.tickers:
        print(json.dumps(verifier(t, instant), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
