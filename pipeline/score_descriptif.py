"""Score descriptif (référentiel BVC Nour) — MODE FANTÔME, ouvert le 28/10/2026.

⚠️ CE SCORE N'ENTRE NI DANS LA NOTE, NI DANS LE SIGNAL, NI DANS LE CLASSEMENT.
Décision d'Abd Moutalib (28/10/2026) : adopter à terme le référentiel de
scoring de BVC Nour à la place de la note v5.3. Étape 1 : le calculer et le
publier À CÔTÉ (`score_descriptif` dans chaque titre de data.json), mesurer ses
fréquences (`pipeline/backtest_score_descriptif.py`), puis seulement, sur
accord et sur preuves (R8), décider de la bascule. Ni `v53`, ni `sig`, ni
`confidence`, ni aucun rang ne lisent ce module.

Le score ne PRÉDIT rien : il DÉCRIT six traits observables d'un titre à la
dernière séance (tendance, élan, activité, liquidité, rentabilité). La
question posée n'est pas « annonce-t-il la hausse ? » mais « les fréquences
observées par tranche sont-elles justes (recalculables, assez de cas, période
dite) et utiles (les tranches se distinguent-elles) ? ».

LA FORMULE (copie de `nour/analytics.py::canonical_score`, version `nour-quant-v1`)
──────────────────────────────────────────────────────────────────────────────
    tendance20   20   cours > MM20                              → 20, sinon 0
    tendance50   15   cours > MM50                              → 15, sinon 0
    momentum     15   RSI14 dans [45 ; 70] → 15 ; [30 ; 45[ → 7,5 ; sinon 0
    activité     10   volume du jour ÷ médiane des 20 séances PRÉCÉDENTES :
                      [0,8 ; 3] → 10 ; < 0,8 → 5 ; > 3 → 2
    liquidité    20   montant médian échangé (20 séances) ≥ 5 MDH → 20 ;
                      ≥ 1 MDH → 10 ; sinon 0
    rentabilité  20   ROE ≥ 12 % → 20 ; ≥ 5 % → 10 ; sinon 0
    valeur = points ÷ poids COUVERTS × 100. Un facteur sans donnée n'hérite
    d'aucun poids. Publiée seulement si couverture ≥ 70 ET titre observable ;
    sinon état PARTIEL et valeur nulle. SUSPENDU / INDISPONIBLE → NON_CALCULABLE.

ÉCARTS ASSUMÉS À NOUR — chacun a une raison, aucun n'est caché
─────────────────────────────────────────────────────────────
1. MM20, MM50 et RSI sont ceux de NOTRE moteur (data.json), pas ceux de Nour :
   · moyennes : même définition (moyenne des N dernières clôtures, séance du
     jour incluse), arrondies à 2 décimales dans les deux cas ;
   · RSI : Wilder, amorçage arithmétique dans les deux cas, MAIS le nôtre ne
     porte que sur les séances ÉCHANGÉES (`pipeline/seance.clotures_echangees`,
     bougies à volume nul et rediffusions écartées) et est arrondi à 1 décimale
     (Nour : toutes les bougies, 2 décimales). Une valeur à 44,96 vaut chez
     nous 45,0 (15 points) et chez Nour 44,96 (7,5). Rare, mais dit.
2. ROE : `ratios_publies.roe_2025.valeur` — résultat net part du groupe de
   l'exercice 2025 ÷ capitaux propres de CLÔTURE, calculé sur les comptes
   déposés à l'AMMC (pièce citée). Choisi parce que c'est LA définition de Nour
   (`fundamentals.py` : « Résultat annuel / capitaux propres de clôture, non
   moyens »). Écartés : `note_fond_metier.criteres.rentabilite` (c'est un ROIC
   pour la plupart des familles, et un ROE sur fonds propres MOYENS pour les
   banques — ni la même grandeur, ni la même base), `roe_12m` (44 titres sur
   80), `fwd.roe_25` (prévision DATA+ du 01/07, jamais un réalisé).
3. Observabilité : Nour exige « aucune alerte de qualité » (`issues` vide) ;
   nous exigeons les mêmes garanties, traduites dans NOS termes — voir
   `etat_donnees()`.
4. Volumes : un split multiplie le nombre d'actions. Les volumes stockés avant
   la date d'effet sont en actions d'avant ; ils sont ramenés en actions
   d'après (`volumes_equivalents`) pour que ni le rapport de volume ni le
   montant échangé (cours ajusté × volume) ne sautent à la date du split.
5. Arrondi du rapport de volume à 2 décimales avant seuil, comme Nour
   (`_round(…, 2)`) : 2,996 compte pour 3,0.

Les fonctions de ce module sont PURES : aucun fichier lu, aucune horloge.
"""
from __future__ import annotations

import math
from statistics import median

VERSION = "descriptif-nour-v1"
REFERENCE = "BVC Nour nour/analytics.py::canonical_score (nour-quant-v1)"

#: (nom, poids) — l'ordre est celui de Nour. Les noms sont ceux de Nour.
FACTEURS = (("tendance20", 20), ("tendance50", 15), ("momentum", 15),
            ("activité", 10), ("liquidité", 20), ("rentabilité", 20))
POIDS = dict(FACTEURS)
assert sum(POIDS.values()) == 100

COUVERTURE_MIN = 70
FENETRE = 20                 # séances de la liquidité et du volume de référence
MIN_ACTIVES = 10             # séances échangées requises sur les 20 (« ready »)
MIN_SEANCES_TENDANCE = 21    # il faut 21 bougies pour 20 variations (Nour)
MIN_SEANCES_HISTORIQUE = 50  # en deçà : « Historique limité » → pas observable
LIQ_HAUT = 5_000_000.0       # DH
LIQ_BAS = 1_000_000.0
ROE_HAUT = 12.0              # %
ROE_BAS = 5.0
RSI_MIN, RSI_MAX, RSI_BAS = 45.0, 70.0, 30.0


def _fr(v, n=2) -> str:
    """Nombre à la française (virgule), pour les libellés de mesure."""
    if v is None:
        return "—"
    return f"{v:.{n}f}".replace(".", ",")


def _fini(v) -> bool:
    return (v is not None and not isinstance(v, bool)
            and isinstance(v, (int, float)) and math.isfinite(v))


# ─────────────────────────── points de chaque facteur ───────────────────────────

def points_tendance(prix, moyenne) -> float:
    """Cours strictement au-dessus de la moyenne → poids plein, sinon 0."""
    return 1.0 if prix > moyenne else 0.0


def points_momentum(rsi: float) -> float:
    """Part du poids (1 ; 0,5 ; 0) : bornes 45 et 70 INCLUSES, 30 incluse."""
    if RSI_MIN <= rsi <= RSI_MAX:
        return 1.0
    if RSI_BAS <= rsi < RSI_MIN:
        return 0.5
    return 0.0


def points_activite(ratio: float) -> float:
    """[0,8 ; 3] → 1 ; < 0,8 → 0,5 ; > 3 → 0,2 (part du poids de 10)."""
    if 0.8 <= ratio <= 3:
        return 1.0
    return 0.5 if ratio < 0.8 else 0.2


def points_liquidite(montant: float) -> float:
    return 1.0 if montant >= LIQ_HAUT else 0.5 if montant >= LIQ_BAS else 0.0


def points_rentabilite(roe: float) -> float:
    return 1.0 if roe >= ROE_HAUT else 0.5 if roe >= ROE_BAS else 0.0


def facteurs(*, prix, ma20, ma50, rsi, ratio_volume, montant_median,
             liquidite_prete, roe) -> dict:
    """{nom: {poids, points, mesure}} — `points` est None si la donnée manque.

    Un facteur absent garde son poids NOMINAL dans le dictionnaire (pour
    qu'on voie ce qui manque) mais ne compte pas dans la couverture.
    """
    out: dict = {}

    def poser(nom, part, mesure):
        w = POIDS[nom]
        out[nom] = {"poids": w, "points": None if part is None else round(part * w, 2),
                    "mesure": mesure}

    p_ok = _fini(prix) and prix > 0
    if p_ok and _fini(ma20):
        poser("tendance20", points_tendance(prix, ma20),
              f"cours {_fr(prix)} {'>' if prix > ma20 else '≤'} MM20 {_fr(ma20)}")
    else:
        poser("tendance20", None, "absent : cours ou MM20 indisponible")
    if p_ok and _fini(ma50):
        poser("tendance50", points_tendance(prix, ma50),
              f"cours {_fr(prix)} {'>' if prix > ma50 else '≤'} MM50 {_fr(ma50)}")
    else:
        poser("tendance50", None, "absent : cours ou MM50 indisponible (moins de 50 séances)")
    if _fini(rsi):
        poser("momentum", points_momentum(rsi), f"RSI(14) {_fr(rsi, 1)}")
    else:
        poser("momentum", None, "absent : RSI indisponible (moins de 15 séances échangées)")
    r = round(ratio_volume, 2) if _fini(ratio_volume) else None
    if r is not None:
        poser("activité", points_activite(r),
              f"volume du jour = {_fr(r)} × la médiane des 20 séances précédentes")
    else:
        poser("activité", None, "absent : médiane de volume des 20 séances précédentes nulle ou indisponible")
    if liquidite_prete and _fini(montant_median):
        poser("liquidité", points_liquidite(montant_median),
              f"montant médian échangé {_fr(montant_median / 1e6)} MDH (20 séances, estimé clôture × quantité)")
    else:
        poser("liquidité", None, "absent : moins de 10 séances échangées sur les 20 dernières")
    if _fini(roe):
        poser("rentabilité", points_rentabilite(roe),
              f"ROE {_fr(roe, 1)} % (exercice 2025, capitaux propres de clôture)")
    else:
        poser("rentabilité", None, "absent : aucun ROE publié sur comptes déposés")
    return out


# ─────────────────────────── observabilité du titre ───────────────────────────

def etat_donnees(*, suspendu=False, stale=False, prix=None, cloture_coherente=True,
                 n_seances=0, liquidite_prete=False, reprise_recente=False) -> tuple:
    """(décision, motif) — SUSPENDU / INDISPONIBLE / LIMITÉ / OBSERVABLE.

    Traduit les garanties de Nour (`engine.analyze`) dans nos termes :
      · SUSPENDU       cotation suspendue au registre (`bvc_config.SUSPENSIONS`) ;
      · INDISPONIBLE   cours périmé (`_meta.stale`), absent, ou en désaccord
                       avec la dernière clôture de nos chandelles ;
      · LIMITÉ         moins de 50 séances d'historique, liquidité non établie
                       (< 10 séances échangées sur les 20 dernières), ou reprise
                       récente (les cours d'avant décrivent un autre régime, R11) ;
      · OBSERVABLE     tout le reste.
    """
    if suspendu:
        return "SUSPENDU", "cotation suspendue"
    if stale:
        return "INDISPONIBLE", "cours périmé (stale) : pas de valeur sur un cours qui n'est pas celui de la dernière séance"
    if not (_fini(prix) and prix > 0):
        return "INDISPONIBLE", "cours absent"
    if not cloture_coherente:
        return "INDISPONIBLE", "cours en désaccord avec la dernière clôture des chandelles"
    if reprise_recente:
        return "LIMITÉ", "reprise de cotation récente : tendance antérieure non comparable"
    if n_seances < MIN_SEANCES_HISTORIQUE:
        return "LIMITÉ", f"historique limité à {n_seances} séances (minimum {MIN_SEANCES_HISTORIQUE})"
    if not liquidite_prete:
        return "LIMITÉ", "liquidité récente insuffisante (moins de 10 séances échangées sur 20)"
    return "OBSERVABLE", None


def score_descriptif(*, prix, ma20, ma50, rsi, ratio_volume, montant_median,
                     liquidite_prete, roe, decision="OBSERVABLE", motif=None) -> dict:
    """Le score. `decision` vient de `etat_donnees()`.

    Renvoie {valeur, etat, couverture_pct, version, facteurs, motif}.
    `etat` : CALCULABLE (valeur publiée) · PARTIEL (valeur nulle) ·
    NON_CALCULABLE (SUSPENDU / INDISPONIBLE, aucun facteur).
    """
    base = {"version": VERSION}
    if decision in ("SUSPENDU", "INDISPONIBLE"):
        return {"valeur": None, "etat": "NON_CALCULABLE", "couverture_pct": 0,
                **base, "facteurs": {}, "motif": motif or decision}
    f = facteurs(prix=prix, ma20=ma20, ma50=ma50, rsi=rsi, ratio_volume=ratio_volume,
                 montant_median=montant_median, liquidite_prete=liquidite_prete, roe=roe)
    couverts = [x for x in f.values() if x["points"] is not None]
    couv = sum(x["poids"] for x in couverts)
    pts = sum(x["points"] for x in couverts)
    if decision == "OBSERVABLE" and couv >= COUVERTURE_MIN:
        etat, valeur, m = "CALCULABLE", round(pts / couv * 100, 2), None
    else:
        etat, valeur = "PARTIEL", None   # une couverture partielle ne doit pas se lire comme une note
        m = motif or (f"couverture {couv} < {COUVERTURE_MIN}" if couv < COUVERTURE_MIN
                      else "titre non observable")
    return {"valeur": valeur, "etat": etat, "couverture_pct": couv, **base,
            "facteurs": f, "motif": m}


# ─────────────────────────── mesures tirées des chandelles ───────────────────────────

def volumes_equivalents(ticker: str, bougies: list, splits: dict | None = None) -> list:
    """Volumes en actions d'APRÈS split : v × ratio avant la date d'effet.

    `splits` : {ticker: [{"date", "ratio"}]} (`bvc_config.SPLITS`). Les cours des
    chandelles stockées sont DÉJÀ ajustés ; leurs volumes, non (voir
    `adjust_splits`). Sans cette correction, cours ajusté × volume brut sous-
    estime le montant échangé de `ratio` avant le split.
    """
    if splits is None:
        from bvc_config import SPLITS as splits  # noqa: N811
    ops = splits.get(ticker) or []
    out = []
    for b in bougies:
        v = b.get("v")
        v = float(v) if _fini(v) else 0.0
        for op in ops:
            if str(b.get("d", ""))[:10] < op["date"]:
                v *= op["ratio"]
        out.append(v)
    return out


def mesures_series(closes: list, vols: list, n_depuis_reprise=None, n_total=None) -> dict:
    """Les entrées de séries du score, à la DERNIÈRE séance des listes.

    `closes`, `vols` : clôtures et volumes ÉQUIVALENTS (voir
    `volumes_equivalents`) de chaque bougie, y compris à volume nul, dans
    l'ordre chronologique ; seules les 21 dernières comptent. `n_total` : nombre
    de bougies de la série entière (défaut : `len(closes)`). `n_depuis_reprise` :
    séances écoulées depuis une reprise de cotation ; la liquidité ne regarde
    alors que celles-là.
    """
    n_total = len(closes) if n_total is None else n_total
    closes, vols = list(closes[-(FENETRE + 1):]), list(vols[-(FENETRE + 1):])
    n = len(closes)
    # Rapport de volume : jour ÷ médiane des 20 séances PRÉCÉDENTES (Nour :
    # `volumes[-1] / median(volumes[-21:-1])`, None si cette médiane est nulle).
    ratio = None
    if n_total >= MIN_SEANCES_TENDANCE and n >= MIN_SEANCES_TENDANCE:
        prec = vols[-21:-1]
        med = median(prec) if any(prec) else 0
        ratio = vols[-1] / med if med else None
    # Liquidité : montant médian des séances ÉCHANGÉES de la fenêtre.
    lo = n - min(int(n_depuis_reprise), n) if (isinstance(n_depuis_reprise, int)
                                               and n_depuis_reprise > 0) else 0
    idx = list(range(max(lo, n - FENETRE), n))
    actives = [i for i in idx if vols[i] > 0]
    montants = [closes[i] * vols[i] for i in actives]
    return {"n_seances": n_total, "ratio_volume": ratio,
            "montant_median": median(montants) if montants else None,
            "seances_actives": len(actives), "fenetre": len(idx),
            "liquidite_prete": len(actives) >= MIN_ACTIVES and len(idx) >= MIN_ACTIVES,
            "derniere_cloture": closes[-1] if closes else None}


def mesures_bougies(bougies: list, volumes: list | None = None, n_depuis_reprise=None) -> dict:
    """`mesures_series` appliquée à une liste de bougies {d, c, v} triées."""
    vols = list(volumes) if volumes is not None else [
        float(b["v"]) if _fini(b.get("v")) else 0.0 for b in bougies]
    m = mesures_series([float(b["c"]) for b in bougies], vols, n_depuis_reprise,
                       n_total=len(bougies))
    m["derniere_date"] = bougies[-1].get("d") if bougies else None
    return m


def roe_publie(rec: dict):
    """ROE de l'exercice 2025 sur comptes déposés (voir l'écart n°2), ou None."""
    r = (rec.get("ratios_publies") or {}).get("roe_2025")
    v = r.get("valeur") if isinstance(r, dict) else None
    return float(v) if _fini(v) else None


def score_titre(rec: dict, bougies: list | None) -> dict:
    """Le score d'un titre de data.json, depuis SES entrées publiées.

    `rec` : l'objet ticker de data.json (price, ma20, ma50, rsi, _meta,
    ratios_publies). `bougies` : liste de dicts {d, o, h, l, c, v} de
    `pipeline/candles/<T>.json` (ou None). Ne lit rien d'autre et ne modifie
    pas `rec`.
    """
    meta = rec.get("_meta") or {}
    bougies = [b for b in (bougies or []) if _fini(b.get("c")) and b.get("c") > 0]
    bougies.sort(key=lambda b: str(b.get("d")))
    reprise = bool(meta.get("reprise_recente"))
    depuis = meta.get("seances_depuis_reprise")
    m = mesures_bougies(bougies, volumes_equivalents(rec.get("symbol") or "", bougies),
                        depuis if reprise else None)
    prix = rec.get("price")
    coherent = (bool(bougies) and _fini(prix)
                and abs(m["derniere_cloture"] - float(prix)) <= 0.001
                and (not meta.get("prix_asof") or m["derniere_date"] == meta.get("prix_asof")))
    decision, motif = etat_donnees(
        suspendu=bool(meta.get("suspendu")), stale=bool(meta.get("stale", True)),
        prix=prix, cloture_coherente=bool(coherent), n_seances=m["n_seances"],
        liquidite_prete=m["liquidite_prete"], reprise_recente=reprise)
    return score_descriptif(
        prix=prix, ma20=rec.get("ma20"), ma50=rec.get("ma50"), rsi=rec.get("rsi"),
        ratio_volume=m["ratio_volume"], montant_median=m["montant_median"],
        liquidite_prete=m["liquidite_prete"], roe=roe_publie(rec),
        decision=decision, motif=motif)


def annexer(tickers: list, bougies_de) -> dict:
    """Pose `score_descriptif` sur chaque titre — et RIEN d'autre (mode fantôme).

    `tickers` : la liste des objets titre de data.json, modifiée en place.
    `bougies_de(symbole)` : les bougies [{d,o,h,l,c,v}] du titre (ou None).
    Tout ou rien : si un titre lève, aucun n'est modifié. Aucun autre champ
    n'est lu en écriture : `v53`, `sig`, `_meta`, l'ordre de la liste restent
    ce qu'ils étaient (test d'invariance dans `tests/test_score_descriptif.py`).
    """
    calcul = {x["symbol"]: score_titre(x, bougies_de(x["symbol"])) for x in tickers}
    for x in tickers:
        x["score_descriptif"] = calcul[x["symbol"]]
    return calcul


# ─────────────────────────── séries (pour le backtest) ───────────────────────────

def masque_echange(opens, highs, lows, closes, volumes) -> list:
    """Miroir EXACT de `pipeline/seance.clotures_echangees` : True = séance retenue.

    Écartées : volume nul, et recopie de la bougie précédente au titre près
    (ouverture, extrêmes, clôture ET quantité). Série sans aucun volume : tout
    est retenu. Testé contre `clotures_echangees` sur les 81 séries.
    """
    n = len(closes)
    if not any(v > 0 for v in volumes):
        return [True] * n
    garde = []
    for i in range(n):
        ok = volumes[i] > 0
        if ok and i > 0 and (closes[i] == closes[i - 1] and volumes[i] == volumes[i - 1]
                             and opens[i] == opens[i - 1] and highs[i] == highs[i - 1]
                             and lows[i] == lows[i - 1]):
            ok = False
        garde.append(ok)
    return garde


def serie_rsi(closes_echangees: list, periode: int = 14) -> list:
    """RSI de Wilder après chaque clôture échangée (None tant que < 15 clôtures).

    Même arithmétique que `update_data.calc_rsi` (amorçage par la moyenne
    arithmétique des 14 premières variations, lissage récursif, arrondi à 1
    décimale), mais INCRÉMENTALE : le RSI à la date t ne dépend que des clôtures
    jusqu'à t — c'est ce qu'exige un backtest sans regard vers l'avenir.
    Testé égal à `calc_rsi` sur la série tronquée à chaque date.
    """
    n = len(closes_echangees)
    out: list = [None] * n
    if n < periode + 1:
        return out
    var = [closes_echangees[i] - closes_echangees[i - 1] for i in range(1, n)]
    gains = [max(d, 0.0) for d in var]
    pertes = [max(-d, 0.0) for d in var]
    mg = sum(gains[:periode]) / periode
    mp = sum(pertes[:periode]) / periode

    def val(mg, mp):
        if mp == 0:
            return 100.0 if mg > 0 else 50.0
        if mg == 0:
            return 0.0
        return round(100.0 - 100.0 / (1.0 + mg / mp), 1)

    out[periode] = val(mg, mp)
    for i in range(periode, len(var)):
        mg = (mg * (periode - 1) + gains[i]) / periode
        mp = (mp * (periode - 1) + pertes[i]) / periode
        out[i + 1] = val(mg, mp)
    return out
