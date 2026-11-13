"""Score BVC unique 0-100 = Nour + l'apport de Boursenews — MODE FANTÔME, 03/11/2026.

Décision d'Abd Moutalib (03/11/2026, R8 accordé sur le principe) : « adopter le
scoring des captures, les mélanger pour avoir un seul score ». Captures :
(1) le score Nour (`pipeline/score_descriptif.py`) ; (2) le « Scoring technique
des valeurs du MASI 20 » de Boursenews — VOLUME, RSI, MOYENNES MOBILES, MACD,
de --- à +++. ⚠️ La méthode de Boursenews n'est PAS publiée : ce module ne la
reproduit pas. Il retient les QUATRE FAMILLES qu'elle nomme, notées selon des
règles écrites ici.

Ni `v53`, ni `sig`, ni le classement ne lisent ce score (R8, la bascule se fera
après le rapport). Il ne PRÉDIT rien : il décrit.

SANS DOUBLE COMPTE — une famille, un facteur
  Nour                      Score BVC
  tendance20 (20)  ┐
  tendance50 (15)  ┘   →    moyennes_mobiles (35) : MM20 15 · MM50 10 · MM200 10
  momentum (15)     →       momentum (15)   (RSI, règle de Nour INCHANGÉE)
  —                 →       macd (10)       NOUVEAU
  activité (10)     →       activité (10)   (volume)
  liquidité (20)    →       liquidité (15)
  rentabilité (20)  →       rentabilité (15)
POIDS_BVC somme à 100. Ces poids sont UNE PROPOSITION : 35 conserve le poids
total des deux tendances de Nour ; le MACD (10) est financé par la liquidité
et la rentabilité (−5 chacune). Aucun n'a été ajusté sur des résultats.

RÈGLES DES FACTEURS NOUVEAUX
  moyennes_mobiles  chaque moyenne vaut son poids si cours > moyenne (strict),
                    sinon 0. Une moyenne indisponible (MM200 : 200 séances) ne
                    compte pas dans la couverture — elle n'hérite d'aucun poids.
  macd              MACD > signal ET histogramme supérieur à celui de la
                    séance précédente → plein ; MACD > signal seul → moitié ;
                    sinon 0. MACD(12, 26, 9), EMA sans correction de départ
                    (la définition de `update_data.calc_macd`), 35 séances.
Mêmes états que Nour : CALCULABLE si couverture ≥ 70 et titre observable ;
PARTIEL (valeur nulle) sinon ; NON_CALCULABLE si suspendu ou cours périmé.

⚠️ MOMENTUM : la règle de Nour (0 point hors [30 ; 70]) est reprise telle
quelle. Le backtest du 28/10 a observé que les zones RSI < 30 et RSI > 70
sur-performent — constat exploratoire, NON corrigé ici : le corriger sur les
mêmes données serait du surapprentissage. Voir le test hors échantillon
proposé dans `pipeline/backtest_score_bvc.py`.
"""
from __future__ import annotations

from . import score_descriptif as nour
from .score_descriptif import _fini, _fr

VERSION = "bvc-score-v1"

#: LA constante unique des poids (somme 100).
POIDS_BVC = (("moyennes_mobiles", 35), ("momentum", 15), ("macd", 10),
             ("activité", 10), ("liquidité", 15), ("rentabilité", 15))
POIDS = dict(POIDS_BVC)
#: répartition interne du facteur « moyennes mobiles » (somme 35)
SOUS_MM = (("MM20", 15), ("MM50", 10), ("MM200", 10))
assert sum(POIDS.values()) == 100 and sum(w for _, w in SOUS_MM) == POIDS["moyennes_mobiles"]
COUVERTURE_MIN = nour.COUVERTURE_MIN
MIN_SEANCES_MACD = 35


# ─────────────────────────── MACD ───────────────────────────

def serie_macd(closes: list, rapide: int = 12, lente: int = 26, signal: int = 9) -> list:
    """[(macd, signal, histogramme) | None] à chaque clôture, causal.

    EMA `adjust=False` (identique à pandas `ewm(span=…, adjust=False)`), donc à
    `update_data.calc_macd` avant arrondi. None tant que < 35 clôtures.
    """
    n = len(closes)
    out: list = [None] * n
    if n == 0:
        return out
    ar, al, asg = 2 / (rapide + 1), 2 / (lente + 1), 2 / (signal + 1)
    er = el = float(closes[0])
    sg = 0.0
    for i, c in enumerate(closes):
        c = float(c)
        if i:
            er = ar * c + (1 - ar) * er
            el = al * c + (1 - al) * el
        m = er - el
        sg = m if i == 0 else asg * m + (1 - asg) * sg
        if i + 1 >= lente + signal:
            out[i] = (m, sg, m - sg)
    return out


def points_macd(macd, sig, hist, hist_prec) -> float:
    """Part du poids : 1 (MACD > signal et histogramme en hausse), 0,5 (MACD > signal), 0."""
    if macd > sig:
        return 1.0 if hist > hist_prec else 0.5
    return 0.0


# ─────────────────────────── facteurs et score ───────────────────────────

def facteurs_bvc(*, prix, ma20, ma50, ma200, rsi, macd, macd_signal, hist, hist_prec,
                 ratio_volume, montant_median, liquidite_prete, roe,
                 mediane_volume=None) -> dict:
    """{nom: {poids, points, mesure}} — `poids` = poids COUVERT (0 si absent)."""
    out: dict = {}
    p_ok = _fini(prix) and prix > 0
    # moyennes mobiles : trois sous-lignes, une seule barre
    pts, couvert, lignes = 0.0, 0, []
    for nom, w, ma in (("MM20", 15, ma20), ("MM50", 10, ma50), ("MM200", 10, ma200)):
        if p_ok and _fini(ma):
            ok = prix > ma
            pts += w if ok else 0
            couvert += w
            lignes.append(f"{nom} {_fr(ma)} {'<' if ok else '≥'} cours")
        else:
            lignes.append(f"{nom} indisponible")
    out["moyennes_mobiles"] = {
        "poids": couvert, "poids_nominal": POIDS["moyennes_mobiles"],
        "points": pts if couvert else None,
        "mesure": f"cours {_fr(prix)} · " + " · ".join(lignes) if couvert
        else "absent : aucune moyenne mobile disponible"}
    if _fini(rsi):
        w = POIDS["momentum"]
        out["momentum"] = {"poids": w, "poids_nominal": w,
                           "points": round(nour.points_momentum(rsi) * w, 2),
                           "mesure": f"RSI(14) {_fr(rsi, 1)}"}
    else:
        out["momentum"] = {"poids": 0, "poids_nominal": POIDS["momentum"], "points": None,
                           "mesure": "absent : RSI indisponible (moins de 15 séances échangées)"}
    w = POIDS["macd"]
    if all(_fini(x) for x in (macd, macd_signal, hist, hist_prec)):
        part = points_macd(macd, macd_signal, hist, hist_prec)
        sens = "au-dessus" if macd > macd_signal else "sous"
        tend = "en hausse" if hist > hist_prec else "en baisse ou stable"
        out["macd"] = {"poids": w, "poids_nominal": w, "points": round(part * w, 2),
                       "mesure": f"MACD {_fr(macd, 3)} {sens} du signal {_fr(macd_signal, 3)} · histogramme {tend}"}
    else:
        out["macd"] = {"poids": 0, "poids_nominal": w, "points": None,
                       "mesure": "absent : moins de 35 séances"}
    r = round(ratio_volume, 2) if _fini(ratio_volume) else None
    w = POIDS["activité"]
    if r is not None:
        # `ratio` et `mediane` en chiffres : le briefing lit ce rapport-ci, et
        # aucun autre, pour qu'un même titre n'ait qu'un rapport d'activité
        # (constat de l'audit du 12/11/2026 : Salafin 13,9× au briefing, 18,93×
        # sur la fiche, deux médianes différentes). Ne change aucun point.
        out["activité"] = {"poids": w, "poids_nominal": w,
                           "points": round(nour.points_activite(r) * w, 2),
                           "ratio": r,
                           "mediane": (round(mediane_volume, 1) if _fini(mediane_volume) else None),
                           "mesure": f"volume du jour = {_fr(r)} × la médiane des 20 séances précédentes"}
    else:
        out["activité"] = {"poids": 0, "poids_nominal": w, "points": None,
                           "mesure": "absent : médiane de volume des 20 séances précédentes nulle ou indisponible"}
    w = POIDS["liquidité"]
    if liquidite_prete and _fini(montant_median):
        out["liquidité"] = {"poids": w, "poids_nominal": w,
                            "points": round(nour.points_liquidite(montant_median) * w, 2),
                            "mesure": f"montant médian échangé {_fr(montant_median / 1e6)} MDH (20 séances, estimé clôture × quantité)"}
    else:
        out["liquidité"] = {"poids": 0, "poids_nominal": w, "points": None,
                            "mesure": "absent : moins de 10 séances échangées sur les 20 dernières"}
    w = POIDS["rentabilité"]
    if _fini(roe):
        out["rentabilité"] = {"poids": w, "poids_nominal": w,
                              "points": round(nour.points_rentabilite(roe) * w, 2),
                              "mesure": f"ROE {_fr(roe, 1)} % (exercice 2025, capitaux propres de clôture)"}
    else:
        out["rentabilité"] = {"poids": 0, "poids_nominal": w, "points": None,
                              "mesure": "absent : aucun ROE publié sur comptes déposés"}
    return out


def score_bvc(*, decision="OBSERVABLE", motif=None, **entrees) -> dict:
    """Le score unique. `entrees` : voir `facteurs_bvc`. Même contrat d'états que Nour."""
    base = {"version": VERSION}
    if decision in ("SUSPENDU", "INDISPONIBLE"):
        return {"valeur": None, "etat": "NON_CALCULABLE", "couverture_pct": 0, **base,
                "facteurs": {}, "motif": motif or decision}
    f = facteurs_bvc(**entrees)
    couv = sum(x["poids"] for x in f.values() if x["points"] is not None)
    pts = sum(x["points"] for x in f.values() if x["points"] is not None)
    if decision == "OBSERVABLE" and couv >= COUVERTURE_MIN:
        etat, valeur, m = "CALCULABLE", round(pts / couv * 100, 2), None
    else:
        etat, valeur = "PARTIEL", None
        m = motif or (f"couverture {couv} < {COUVERTURE_MIN}" if couv < COUVERTURE_MIN
                      else "titre non observable")
    return {"valeur": valeur, "etat": etat, "couverture_pct": couv, **base, "facteurs": f, "motif": m}


# ─────────────────────────── le titre de data.json ───────────────────────────

def rupture_de_reference(ticker: str, bougies: list) -> dict | None:
    """Moyennes mobiles qui traversent une RÉFÉRENCE REMISE À NEUF.

    Audit externe du 12/11/2026 : CMT affichait 100 % de couverture alors que
    ses MM50 et MM200 incorporent des cours d'avant la reprise du 16/09/2026,
    où l'AMMC a fixé une référence neuve (2 217 DH contre 4 501 avant la
    suspension, R10 seconde précision, R11). La série n'est PAS rétro-ajustée
    — la perte des porteurs est réelle — mais une moyenne qui mêle les deux
    régimes ne compare pas le cours à son propre passé récent. Le fait vient du
    registre `bvc_config.SUSPENSIONS` (champ `reference_impliquee`), jamais
    d'un saut de prix. Rend {"reprise", "seances", "moyennes"} ou None ; ne
    change AUCUN point du score (R8) : c'est une mention.
    """
    try:
        from bvc_config import SUSPENSIONS
    except ImportError:
        return None
    reprises = [e.get("reprise") for e in SUSPENSIONS.get(ticker or "", [])
                if e.get("reprise") and e.get("reference_impliquee") is not None]
    if not reprises:
        return None
    reprise = max(reprises)
    n = sum(1 for b in bougies or [] if str(b.get("d") or "") >= reprise)
    moyennes = [nom for nom, fen in (("MM20", 20), ("MM50", 50), ("MM200", 200)) if n < fen]
    return {"reprise": reprise, "seances": n, "moyennes": moyennes} if moyennes else None


def score_titre_bvc(rec: dict, bougies: list | None) -> dict:
    """Score BVC d'un titre de data.json, depuis ses entrées publiées et ses chandelles."""
    meta = rec.get("_meta") or {}
    bg = [b for b in (bougies or []) if _fini(b.get("c")) and b.get("c") > 0]
    bg.sort(key=lambda b: str(b.get("d")))
    reprise = bool(meta.get("reprise_recente"))
    depuis = meta.get("seances_depuis_reprise")
    m = nour.mesures_bougies(bg, nour.volumes_equivalents(rec.get("symbol") or "", bg),
                             depuis if reprise else None)
    prix = rec.get("price")
    coherent = (bool(bg) and _fini(prix) and abs(m["derniere_cloture"] - float(prix)) <= 0.001
                and (not meta.get("prix_asof") or m["derniere_date"] == meta.get("prix_asof")))
    decision, motif = nour.etat_donnees(
        suspendu=bool(meta.get("suspendu")), stale=bool(meta.get("stale", True)),
        prix=prix, cloture_coherente=bool(coherent), n_seances=m["n_seances"],
        liquidite_prete=m["liquidite_prete"], reprise_recente=reprise)
    mc = serie_macd([float(b["c"]) for b in bg])
    macd = sig = hist = hprec = None
    if len(mc) >= 2 and mc[-1] is not None and mc[-2] is not None:
        macd, sig, hist = mc[-1]
        hprec = mc[-2][2]
    out = score_bvc(
        prix=prix, ma20=rec.get("ma20"), ma50=rec.get("ma50"), ma200=rec.get("ma200"),
        rsi=rec.get("rsi"), macd=macd, macd_signal=sig, hist=hist, hist_prec=hprec,
        ratio_volume=m["ratio_volume"], montant_median=m["montant_median"],
        liquidite_prete=m["liquidite_prete"], roe=nour.roe_publie(rec),
        mediane_volume=m.get("mediane_volume"),
        decision=decision, motif=motif)
    rup = rupture_de_reference(rec.get("symbol") or "", bg)
    mm = (out.get("facteurs") or {}).get("moyennes_mobiles")
    if rup and mm and mm.get("points") is not None:
        a, j, mo = rup["reprise"].split("-")
        mm["rupture"] = rup
        mm["mesure"] += (f" · ⚠ {', '.join(rup['moyennes'])} incluent des cours d'avant la reprise du "
                         f"{mo}/{j}/{a} (référence remise à neuf par l'AMMC, {rup['seances']} séances depuis)")
    return out


def annexer_bvc(tickers: list, bougies_de) -> dict:
    """Pose `score_bvc` sur chaque titre — et RIEN d'autre. Tout ou rien."""
    calcul = {x["symbol"]: score_titre_bvc(x, bougies_de(x["symbol"])) for x in tickers}
    for x in tickers:
        x["score_bvc"] = calcul[x["symbol"]]
    return calcul
