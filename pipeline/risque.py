"""Mesures de risque par titre — descriptives, hors note.

Ouvert le 14/10/2026. Tout est calculé depuis NOS chandelles
(`pipeline/candles/*.json`) et l'historique du MASI
(`pipeline/masi_history.json`). Aucune autre source.

⚠️ CES MESURES N'ENTRENT PAS DANS LA NOTE (R8). Ni le score, ni le signal, ni
la confiance, ni les poids ne les lisent. Elles décrivent ce qui s'est passé
sur l'année écoulée — fréquences observées, avec leur effectif et leur période
— conformément à la Vision Produit : on ne prédit pas, on mesure.

Les fonctions de ce module sont PURES : elles ne lisent aucun fichier et ne
dépendent pas de l'horloge. `update_data.py` leur passe les séries.

CONVENTIONS — chacune répond à un piège déjà rencontré
───────────────────────────────────────────────────────
· **Le calendrier des séances se déduit du marché, pas du titre.** Une date est
  une séance réelle si au moins `MIN_TITRES_SEANCE` titres y ont échangé (même
  seuil que `pipeline/seance.py`), hors week-end, hors férié à date fixe, hors
  séance annulée ou sans cotation des registres de `bvc_config`. Un jour absent
  des chandelles d'un titre n'est PAS, à lui seul, une séance : un férié ou un
  week-end n'entre jamais dans un décompte.

· **Une bougie à volume nul n'est pas un mouvement.** Sa clôture est une
  recopie (séance fantôme, référence rediffusée). Elle est écartée des
  rendements et comptée. Le rendement se calcule d'une clôture ÉCHANGÉE à la
  suivante : c'est la définition même de la variation à la BVC, dont le cours
  de référence est le dernier cours coté. Le plafond de ±10 % (R10) s'y
  applique donc, même quand des séances sans échange les séparent — et les
  données le confirment : aucun écart entre 10,0 % et 15 % sur 80 séries.

· **Un saut de plus de 10 % n'entre pas dans les rendements.** R10 : sur un
  titre coté, c'est une erreur de source ou une opération sur titres. Il est
  exclu, compté, et daté. Une reprise de cotation inscrite au registre
  (`SUSPENSIONS[...]["reprise"]`) est traitée À PART : la fenêtre recommence
  à la reprise, parce que les cours d'avant décrivent un autre régime de prix
  (R11). Les splits du registre (`SPLITS`) sont déjà ajustés dans les
  chandelles stockées ; un split non ajusté apparaîtrait ici comme un saut
  exclu, et se verrait.

· **Effectif minimal : 120 rendements** (≈ six mois de séances) pour toute
  mesure sur un an. Trois raisons, mesurables :
    – la VaR 95 % historique lit la queue à 5 % : à 120 rendements elle repose
      sur 6 observations, et la CVaR en fait la moyenne ; en deçà, un seul
      événement fait le chiffre ;
    – l'erreur relative sur un écart-type vaut ≈ 1/√(2n) : 6,5 % à n = 120,
      soit ±1,3 point sur une volatilité de 20 % ;
    – sous 120, « un an » décrirait moins de la moitié de l'année.
  Même seuil pour la liquidité, dont la fenêtre fait 120 séances : un titre
  dont nos chandelles ne couvrent pas les six mois entiers n'a pas de mesure
  « sur six mois ».

· **Le montant échangé n'existe pas dans nos chandelles** — `v` est une
  QUANTITÉ de titres (Famille 18 d'ERRORS.md). L'approcher par quantité ×
  clôture mélangerait deux définitions (LEARNINGS, 25/09/2026). La liquidité
  publie donc la quantité médiane, et le ratio d'Amihud reste `null`, motif
  écrit.
"""
from __future__ import annotations

import math
from datetime import date
from statistics import mean, median, stdev

from bvc_config import est_ferie_fixe, seance_annulee, seance_sans_cotation

VERSION = "risque-v1-2026-10-14"

FENETRE_AN = 250            # séances : un an glissant au plus
FENETRE_LIQUIDITE = 120     # séances : six mois
ANNUALISATION = 250         # séances par an, pour la volatilité
MIN_RENDEMENTS = 120        # voir l'en-tête : VaR 95 % sur 6 obs. au moins
MIN_SEANCES_LIQUIDITE = 120
MIN_TITRES_SEANCE = 20      # même seuil que pipeline/seance.py
SEUIL_SAUT = 0.10           # R10
_TOLERANCE = 1e-9           # arrondi flottant, pas une marge de règle
NIVEAU_VAR = 0.95

MOTIF_MONTANT = ("montant échangé absent de nos chandelles : elles portent la "
                 "quantité de titres seulement ; l'approcher par quantité × "
                 "clôture mélangerait deux définitions")
MOTIF_AMIHUD = ("non calculé : le ratio d'Amihud exige le montant échangé en "
                "dirhams, absent de nos chandelles (quantité seulement)")


def _vol(b) -> float:
    try:
        v = float(b.get("v") or 0)
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) else 0.0


def _clo(b) -> float | None:
    try:
        c = float(b.get("c"))
    except (TypeError, ValueError):
        return None
    return c if math.isfinite(c) and c > 0 else None


def est_jour_ouvre(d: str) -> bool:
    """Ni week-end, ni férié fixe, ni séance annulée ou sans cotation."""
    try:
        if date.fromisoformat(d[:10]).weekday() >= 5:
            return False
    except (TypeError, ValueError):
        return False
    return not (est_ferie_fixe(d) or seance_annulee(d) or seance_sans_cotation(d))


def calendrier_seances(series: dict, min_titres: int = MIN_TITRES_SEANCE) -> list:
    """Les séances réelles de la BVC, déduites des chandelles de TOUT le marché.

    `series` : {ticker: [bougie, ...]}. Une date est retenue si au moins
    `min_titres` titres y portent une bougie à volume strictement positif, et
    si elle passe `est_jour_ouvre`. Renvoie la liste triée des dates.
    """
    compte: dict = {}
    for bougies in (series or {}).values():
        vues = set()
        for b in bougies or []:
            d = str(b.get("d", ""))[:10]
            if not d or d in vues or _vol(b) <= 0:
                continue
            vues.add(d)
            compte[d] = compte.get(d, 0) + 1
    return sorted(d for d, n in compte.items()
                  if n >= min_titres and est_jour_ouvre(d))


def _mesure_nulle(motif: str, **extra) -> dict:
    return {"valeur": None, "n": 0, "du": None, "au": None, "motif": motif, **extra}


def _nul_partout(code: str, texte: str, au: str | None) -> dict:
    return {
        "version": VERSION, "asof": au,
        "motif": {"code": code, "texte": texte},
        "rendements": None,
        "volatilite": _mesure_nulle(texte),
        "beta": _mesure_nulle(texte, correlation=None),
        "perte_max": _mesure_nulle(texte, sommet=None, creux=None),
        "var95": _mesure_nulle(texte, cvar=None),
        "liquidite": _mesure_nulle(texte, quantite_mediane=None, montant_median=None,
                                   motif_montant=MOTIF_MONTANT, seances=0,
                                   sans_echange=None, dont_volume_nul=None,
                                   dont_sans_bougie=None, amihud=None,
                                   motif_amihud=MOTIF_AMIHUD),
    }


def _fr(d: str | None) -> str:
    return "/".join(reversed(d.split("-"))) if d else "—"


def mesurer_risque(bougies: list, calendrier: list, masi: dict | None = None, *,
                   jusqu_au: str | None = None, suspension: dict | None = None,
                   reprise: str | None = None) -> dict:
    """Le bloc `risque` d'un titre.

    bougies     : chandelles du titre, [{"d","o","h","l","c","v"}, ...]
    calendrier  : séances réelles (`calendrier_seances`)
    masi        : {date: valeur} de l'indice
    jusqu_au    : dernière séance prise en compte (incluse) ; par défaut la
                  dernière du calendrier. Le moteur y passe la dernière séance
                  CLOSE, jamais une séance en cours.
    suspension  : entrée du registre `SUSPENSIONS` en vigueur, ou None
    reprise     : date de la dernière reprise de cotation inscrite au registre

    Chaque mesure porte `valeur`, `n`, `du`, `au` et `motif` (None si mesurée).
    """
    cal = [d for d in (calendrier or []) if jusqu_au is None or d <= jusqu_au]
    au = cal[-1] if cal else None
    if suspension:
        return _nul_partout(
            "suspendu",
            f"titre suspendu depuis le {_fr(suspension.get('depuis'))} "
            f"({suspension.get('motif', 'motif non précisé')}) : un titre qui ne "
            "cote pas n'a pas de risque de marché mesurable", au)
    if not cal:
        return _nul_partout("aucune_seance", "aucune séance dans le calendrier", au)

    serie = {}
    for b in bougies or []:
        d = str(b.get("d", ""))[:10]
        if d:
            serie[d] = b                       # la dernière occurrence fait foi
    premiere = min(serie) if serie else None
    if premiere is None:
        return _nul_partout("aucune_chandelle", "aucune chandelle pour ce titre", au)

    rang = {d: i for i, d in enumerate(cal)}
    reprise_dans = reprise if (reprise and reprise <= au) else None

    def _debut(fenetre: list) -> tuple:
        """Début effectif d'une fenêtre, et ce qui l'a raccourcie."""
        debut, cause = fenetre[0], None
        if reprise_dans and reprise_dans > debut:
            debut, cause = reprise_dans, "reprise"
        if premiere > debut:
            debut, cause = premiere, "historique"
        return debut, cause

    def _motif_court(n: int, minimum: int, cause, quoi: str) -> tuple:
        if cause == "reprise":
            return ("reprise_trop_recente",
                    f"reprise de cotation le {_fr(reprise_dans)} : {n} {quoi} "
                    f"depuis, il en faut {minimum} ; les cours d'avant la "
                    "suspension décrivent un autre régime de prix (R11)")
        if cause == "historique":
            return ("historique_court",
                    f"nos chandelles commencent le {_fr(premiere)} : {n} {quoi}, "
                    f"il en faut {minimum}")
        return ("effectif_insuffisant",
                f"{n} {quoi} sur la période, il en faut {minimum}")

    # ── Rendements sur un an ─────────────────────────────────────────────
    fen_an = cal[-FENETRE_AN:]
    debut_an, cause_an = _debut(fen_an)
    dates_an = [d for d in fen_an if d >= debut_an]
    dans = [serie[d] for d in dates_an if d in serie]
    volume_nul = [b for b in dans if _vol(b) <= 0]
    echangees = [b for b in dans if _vol(b) > 0 and _clo(b) is not None]

    rendements, sauts, multi = [], [], 0
    for a, b in zip(echangees, echangees[1:]):
        r = _clo(b) / _clo(a) - 1
        da, db = str(a["d"])[:10], str(b["d"])[:10]
        if abs(r) > SEUIL_SAUT + _TOLERANCE:
            sauts.append({"du": da, "au": db, "variation": round(100 * r, 2)})
            continue
        # ⚠️ 14/10/2026 (diagnostic externe) : une « VaR à 1 jour » ne mélange
        # pas des rendements qui couvrent plusieurs séances (titre non échangé
        # entre deux). Mesuré : 10 titres sur 65 au-delà de 10 % de tels
        # rendements, MGL 3,98 % publié contre 3,25 % sur une séance. On les
        # compte, on les écarte de la VaR et de la volatilité.
        if rang[db] - rang[da] > 1:
            multi += 1
            continue
        rendements.append((da, db, r))

    n = len(rendements)
    bloc_r = {
        "n": n,
        "du": rendements[0][0] if rendements else None,
        "au": rendements[-1][1] if rendements else None,
        "exclus_volume_nul": len(volume_nul),
        "exclus_saut": len(sauts),
        "sauts": sauts,
        "sur_plusieurs_seances": multi,            # écartés (voir plus haut)
        "seances_fenetre": len(dates_an),
    }

    if n < MIN_RENDEMENTS:
        code, texte = _motif_court(n, MIN_RENDEMENTS, cause_an, "rendements d'une séance")
        if multi:
            texte += (f" ; {multi} rendement(s) couvrant plusieurs séances (titre non "
                      "échangé entre deux) écarté(s) d'une mesure à 1 jour")
        motif_global = {"code": code, "texte": texte}
        volatilite = _mesure_nulle(texte, n=n)
        var95 = _mesure_nulle(texte, n=n, cvar=None)
        perte_max = _mesure_nulle(texte, n=n, sommet=None, creux=None)
    else:
        motif_global = None
        r_seuls = [r for _, _, r in rendements]
        du, au_r = rendements[0][0], rendements[-1][1]
        volatilite = {"valeur": round(100 * stdev(r_seuls) * math.sqrt(ANNUALISATION), 2),
                      "n": n, "du": du, "au": au_r, "motif": None}
        tri = sorted(r_seuls)
        # ⚠️ `round` avant `ceil` : (1 − 0,95) vaut 0,050000000000000044 en
        # flottant, et 40 rendements donneraient une queue de 3 au lieu de 2.
        k = max(1, math.ceil(round((1 - NIVEAU_VAR) * n, 9)))
        var95 = {"valeur": round(-100 * tri[k - 1], 2),
                 "cvar": round(-100 * mean(tri[:k]), 2),
                 "n": n, "n_queue": k, "du": du, "au": au_r, "motif": None}
        if sauts:
            texte = (f"{len(sauts)} saut(s) de plus de 10 % non expliqué(s) dans la "
                     "fenêtre : les clôtures de part et d'autre ne sont pas "
                     "comparables (R10)")
            perte_max = _mesure_nulle(texte, n=len(echangees), sommet=None, creux=None)
        else:
            pic, pic_d, pire = None, None, (0.0, None, None, None, None)
            for b in echangees:
                c, d = _clo(b), str(b["d"])[:10]
                if pic is None or c > pic:
                    pic, pic_d = c, d
                baisse = 1 - c / pic
                if baisse > pire[0]:
                    pire = (baisse, pic_d, pic, d, c)
            perte_max = {
                "valeur": round(100 * pire[0], 2),
                "sommet": {"d": pire[1], "c": pire[2]} if pire[1] else None,
                "creux": {"d": pire[3], "c": pire[4]} if pire[3] else None,
                "n": len(echangees), "du": str(echangees[0]["d"])[:10],
                "au": str(echangees[-1]["d"])[:10], "motif": None,
            }

    # ── Bêta et corrélation contre le MASI : intervalles IDENTIQUES ─────
    # Le rendement du MASI est pris sur le MÊME intervalle que celui du
    # titre (de sa clôture échangée précédente à la suivante). Une date
    # absente de l'historique du MASI retire la paire : aucune interpolation.
    paires = []
    for da, db, r in rendements:
        ma, mb = (masi or {}).get(da), (masi or {}).get(db)
        if ma and mb and ma > 0 and mb > 0:
            paires.append((da, db, r, mb / ma - 1))
    nc = len(paires)
    if n < MIN_RENDEMENTS:
        beta = _mesure_nulle(volatilite["motif"], n=nc, correlation=None)
    elif nc < MIN_RENDEMENTS:
        beta = _mesure_nulle(f"{nc} séances communes avec le MASI, il en faut "
                             f"{MIN_RENDEMENTS}", n=nc, correlation=None)
    else:
        x = [p[3] for p in paires]
        y = [p[2] for p in paires]
        mx, my = mean(x), mean(y)
        cov = sum((a - mx) * (b - my) for a, b in zip(x, y)) / (nc - 1)
        vx, vy = stdev(x) ** 2, stdev(y) ** 2
        beta = {"valeur": round(cov / vx, 3) if vx > 0 else None,
                "correlation": round(cov / math.sqrt(vx * vy), 3) if vx > 0 and vy > 0 else None,
                "n": nc, "du": paires[0][0], "au": paires[-1][1], "motif": None}

    # ── Liquidité sur six mois ───────────────────────────────────────────
    fen_l = cal[-FENETRE_LIQUIDITE:]
    debut_l, cause_l = _debut(fen_l)
    seances_l = [d for d in fen_l if d >= debut_l]
    if len(seances_l) < MIN_SEANCES_LIQUIDITE:
        code, texte = _motif_court(len(seances_l), MIN_SEANCES_LIQUIDITE, cause_l,
                                   "séances couvertes")
        liquidite = _mesure_nulle(texte, n=len(seances_l), quantite_mediane=None,
                                  montant_median=None, motif_montant=MOTIF_MONTANT,
                                  seances=len(seances_l), sans_echange=None,
                                  dont_volume_nul=None, dont_sans_bougie=None,
                                  amihud=None, motif_amihud=MOTIF_AMIHUD)
        if motif_global is None:
            motif_global = {"code": code, "texte": texte, "portee": "liquidite"}
    else:
        quantites, v_nul, absentes = [], 0, 0
        for d in seances_l:
            b = serie.get(d)
            if b is None:
                absentes += 1
                quantites.append(0.0)
            elif _vol(b) <= 0:
                v_nul += 1
                quantites.append(0.0)
            else:
                quantites.append(_vol(b))
        liquidite = {
            "valeur": median(quantites), "quantite_mediane": median(quantites),
            "montant_median": None, "motif_montant": MOTIF_MONTANT,
            "seances": len(seances_l), "n": len(seances_l),
            "sans_echange": v_nul + absentes, "dont_volume_nul": v_nul,
            "dont_sans_bougie": absentes,
            "du": seances_l[0], "au": seances_l[-1],
            "amihud": None, "motif_amihud": MOTIF_AMIHUD, "motif": None,
        }

    return {
        "version": VERSION, "asof": au, "motif": motif_global,
        "rendements": bloc_r, "volatilite": volatilite, "beta": beta,
        "perte_max": perte_max, "var95": var95, "liquidite": liquidite,
    }


def derniere_reprise(periodes: list | None) -> str | None:
    """La date de la dernière reprise inscrite au registre, ou None."""
    reprises = [p["reprise"] for p in (periodes or []) if p.get("reprise")]
    return max(reprises) if reprises else None


def mesurer_cote(series: dict, masi: dict | None, tickers: list, *,
                 jusqu_au: str | None = None) -> dict:
    """Le bloc `risque` de chaque titre de `tickers`, sur un calendrier commun.

    `series` : {ticker: [bougie, ...]} — TOUTES les séries disponibles, pas
    seulement celles des `tickers` : le calendrier se déduit du marché entier.
    Les registres `SUSPENSIONS` (suspension en vigueur, dernière reprise) sont
    lus dans `bvc_config`, à la date de la dernière séance retenue.
    """
    from bvc_config import SUSPENSIONS, est_suspendu
    cal = [d for d in calendrier_seances(series) if jusqu_au is None or d <= jusqu_au]
    au = cal[-1] if cal else jusqu_au
    return {t: mesurer_risque(series.get(t) or [], cal, masi, jusqu_au=au,
                              suspension=est_suspendu(t, au) if au else None,
                              reprise=derniere_reprise(SUSPENSIONS.get(t)))
            for t in tickers}
