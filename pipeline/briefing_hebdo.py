#!/usr/bin/env python3
"""Le bilan de la semaine — même règle que le quotidien : constater, pas expliquer.

⚠️ CE QU'IL PEUT DIRE AUJOURD'HUI, ET CE QU'IL NE PEUT PAS
──────────────────────────────────────────────────────────
Le bilan hebdomadaire est limité par ce que le projet a historisé, et cette
limite doit être ÉNONCÉE DANS LE BILAN, pas cachée dans un fichier de code.

    mesurable          l'indice sur la semaine        191 séances d'historique
                       la performance par titre       79 séries de chandelles
                       les publications de la semaine  300 articles collectés

    PAS mesurable      la largeur jour après jour      1 séance d'historique
                       les signaux qui ont changé      1 séance d'historique

Les deux dernières le deviendront quand `marche_history` et `score_history`
auront accumulé des séances — ouverts les 24 et 25/09/2026. **On ne les
simule pas en attendant** : reconstituer un signal passé depuis les données
d'aujourd'hui donnerait au modèle la connaissance du futur, et c'est
exactement le piège que le backtest documente.

⚠️ LA SEMAINE SE COMPTE EN SÉANCES, PAS EN JOURS
Un lundi férié ou une séance annulée ne sont pas des jours de bourse. Compter
« sept jours en arrière » ferait tantôt quatre séances, tantôt six, et la
performance affichée ne porterait pas toujours sur la même chose. On prend
donc les séances réellement cotées.

⚠️ LA RÉFÉRENCE EST LA DERNIÈRE CLÔTURE **AVANT** LA SEMAINE
Prendre la première clôture de la semaine comme base exclurait le mouvement du
lundi — le plus gros de la semaine une fois sur cinq. C'est une erreur
classique et silencieuse : le chiffre reste plausible, il est simplement faux.
"""

from __future__ import annotations

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CANDLES = RACINE / "pipeline" / "candles"

# Une performance hebdomadaire n'est publiée que si le titre a coté au moins
# deux fois dans la semaine. Sur une seule séance, l'écart mesuré porte
# autant sur l'illiquidité que sur le titre.
MIN_SEANCES_SEMAINE = 2

# Combien de titres au palmarès. Au-delà, ce n'est plus un bilan, c'est la
# cote entière triée.
TAILLE_PALMARES = 5


def _lire(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def seances_de_la_semaine(dates: list, fin: str, n_max=5) -> list:
    """Les séances cotées de la semaine se terminant à `fin`, incluse.

    ⚠️ Déduit des DATES RÉELLEMENT PRÉSENTES, sans calendrier de fériés. Les
    jours fériés marocains suivent en partie le calendrier lunaire et une
    liste codée en dur ne serait pas maintenue — c'est le raisonnement qui a
    déjà servi pour les séances fantômes.
    """
    from datetime import date
    try:
        f = date.fromisoformat(str(fin)[:10])
    except (TypeError, ValueError):
        return []
    # Le lundi de la semaine de `fin`. `weekday()` vaut 0 le lundi.
    from datetime import timedelta
    lundi = f - timedelta(days=f.weekday())
    dans = []
    for d in sorted(set(str(x)[:10] for x in dates)):
        try:
            j = date.fromisoformat(d)
        except ValueError:
            continue
        if lundi <= j <= f:
            dans.append(d)
    return dans[-n_max:]


def _perf(serie: list, semaine: list):
    """(perf en %, référence, clôture, nombre de séances cotées) ou None.

    `serie` : [(date, clôture)] triée. `semaine` : les dates de la semaine.

    ⚠️ La référence est la dernière clôture ANTÉRIEURE à la semaine. Prendre
    la première clôture de la semaine exclurait le mouvement du lundi.
    """
    if not serie or not semaine:
        return None
    debut = semaine[0]
    avant = [c for d, c in serie if d < debut]
    dedans = [(d, c) for d, c in serie if debut <= d <= semaine[-1]]
    if not avant or len(dedans) < MIN_SEANCES_SEMAINE:
        return None
    ref, fin = avant[-1], dedans[-1][1]
    if not ref:
        return None
    return {"perf_pct": round((fin / ref - 1) * 100, 2),
            "reference": round(ref, 2), "cloture": round(fin, 2),
            "seances": len(dedans)}


def series_titres(dossier=None) -> dict:
    """{ticker: [(date, clôture)]} depuis les chandelles publiées."""
    out = {}
    for f in sorted(Path(dossier or CANDLES).glob("*.json")):
        s = _lire(f)
        if not isinstance(s, list):
            continue
        serie = [(str(b.get("d"))[:10], float(b["c"])) for b in s
                 if b.get("c") and b.get("d") and float(b["c"]) > 0]
        if serie:
            out[f.stem] = sorted(serie)
    return out


def indice_semaine(masi_history: dict, semaine: list):
    s = (masi_history or {}).get("seances") or {}
    serie = sorted((d, float(v)) for d, v in s.items()
                   if isinstance(v, (int, float)))
    return _perf(serie, semaine)


def composer(data: dict, masi_history=None, series=None,
             articles=None) -> dict:
    """Le bilan de la semaine. Fonction pure si on lui passe ses entrées."""
    from pipeline.briefing import actualites, charger_articles

    titres = data.get("tickers") or []
    fin = max((str((x.get("_meta") or {}).get("prix_asof") or "")
               for x in titres), default="")
    mh = masi_history if masi_history is not None else \
        (_lire(RACINE / "pipeline" / "masi_history.json") or {})
    sr = series if series is not None else series_titres()

    # ⚠️ Les dates de séance viennent de l'indice ET des titres réunis : un
    # jour où l'indice manque reste une séance si les titres ont coté.
    toutes = set((mh.get("seances") or {})) | {d for s in sr.values() for d, _ in s}
    semaine = seances_de_la_semaine(sorted(toutes), fin)

    perfs = []
    meta = {x.get("symbol"): (x.get("_meta") or {}) for x in titres}
    noms = {x.get("symbol"): x.get("name") for x in titres}
    for sym, serie in sr.items():
        p = _perf(serie, semaine)
        if not p:
            continue
        m = meta.get(sym) or {}
        perfs.append({
            "symbol": sym, "name": noms.get(sym), **p,
            # ⚠️ R11 — une reprise de cotation après OPA change la RÉFÉRENCE,
            # pas seulement le cours. La performance affichée est réelle, mais
            # elle ne se compare pas aux autres : on le signale plutôt que de
            # la retirer du classement, parce que la retirer effacerait un
            # mouvement qui a bien eu lieu.
            "reprise_recente": bool(m.get("reprise_recente")),
        })
    perfs.sort(key=lambda z: -z["perf_pct"])

    b = {
        "type": "hebdomadaire",
        "semaine": {"seances": semaine, "n": len(semaine)},
        "indice": indice_semaine(mh, semaine),
        "hausses": perfs[:TAILLE_PALMARES],
        "baisses": list(reversed(perfs[-TAILLE_PALMARES:])) if perfs else [],
        "n_titres": len(perfs),
        "actualites": actualites(
            articles if articles is not None else charger_articles(),
            fin, jours=7),
        "constats": [],
        # ⚠️ ÉNONCÉ DANS LE PRODUIT, pas seulement dans le code.
        "non_mesurable": [
            "l'évolution de la largeur de marché sur la semaine — son "
            "historique a commencé le 24/09/2026 et ne couvre pas encore "
            "sept jours",
            "les signaux qui ont changé dans la semaine — le journal des "
            "scores a commencé le 25/09/2026",
            "POURQUOI la semaine a été ce qu'elle a été — ce bilan mesure "
            "des cours et des volumes, il ne mesure pas de causes",
        ],
    }

    if not semaine:
        b["constats"].append("Aucune séance cotée identifiée sur la semaine.")
        return b

    i = b["indice"]
    if i:
        b["constats"].append(
            f"Sur {_pluriel(len(semaine), 'séance')} cotée"
            f"{'s' if len(semaine) > 1 else ''}, l'indice passe de "
            f"{_fr(i['reference'])} à {_fr(i['cloture'])}, soit "
            f"{_fr(i['perf_pct'])} %.")
    else:
        b["non_mesurable"].insert(
            0, "la performance de l'indice sur la semaine — son historique ne "
               "couvre pas la séance de référence")

    if perfs:
        larges = [x for x in perfs if x["perf_pct"] > 0]
        b["constats"].append(
            f"{_pluriel(len(larges), 'titre')} sur {len(perfs)} "
            f"termine{'nt' if len(larges) > 1 else ''} la semaine en hausse.")
        h, bs = perfs[0], perfs[-1]
        b["constats"].append(
            f"Plus forte hausse {h['symbol']} à {_fr(h['perf_pct'])} %, plus "
            f"forte baisse {bs['symbol']} à {_fr(bs['perf_pct'])} %.")
        if any(x["reprise_recente"] for x in perfs[:TAILLE_PALMARES]):
            b["constats"].append(
                "⚠️ Un titre du palmarès vient de reprendre sa cotation : sa "
                "référence a été fixée par l'autorité de marché, sa "
                "performance ne se compare pas aux autres.")

    a = b["actualites"]
    n = len(a.get("titres") or []) + len(a.get("autres") or [])
    if n:
        b["constats"].append(
            f"{_pluriel(n, 'publication')} retenue"
            f"{'s' if n > 1 else ''} sur la semaine, dont "
            f"{sum(1 for x in a.get('titres') or [] if x['officielle'])} "
            f"de source officielle.")
    return b


def _fr(x, d=2):
    from pipeline.briefing import _fr as f
    return f(x, d)


def _pluriel(n, s, p=None):
    from pipeline.briefing import _pluriel as f
    return f(n, s, p)


def ecrire(b: dict, chemin=None) -> str:
    """Publie le bilan là où le terminal le lira.

    ⚠️ Fichier distinct du quotidien : les deux doivent pouvoir coexister, et
    un bilan de semaine ne remplace pas la lecture de la dernière séance.
    """
    p = Path(chemin) if chemin else (RACINE / "briefing_hebdo.json")
    p.write_text(json.dumps(b, ensure_ascii=False, separators=(",", ":")),
                 encoding="utf-8")
    return str(p)


def texte(b: dict) -> str:
    L = [f"BILAN DE LA SEMAINE — {b['semaine']['n']} séance(s) cotée(s)"]
    for c in b.get("constats") or []:
        L.append(f"   · {c}")
    if b.get("hausses"):
        L.append("")
        L.append("   Hausses de la semaine")
        for x in b["hausses"]:
            L.append(f"     {x['symbol']:<6} {_fr(x['perf_pct']):>8} %")
    if b.get("baisses"):
        L.append("   Baisses de la semaine")
        for x in b["baisses"]:
            L.append(f"     {x['symbol']:<6} {_fr(x['perf_pct']):>8} %")
    if b.get("non_mesurable"):
        L.append("")
        L.append("   Ce que ce bilan ne dit pas :")
        for x in b["non_mesurable"]:
            L.append(f"     — {x}.")
    return "\n".join(L)
