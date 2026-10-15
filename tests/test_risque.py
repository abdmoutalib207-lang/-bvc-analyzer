"""Mesures de risque par titre (`pipeline/risque.py`) — 14/10/2026.

Cas synthétiques calculés à la main, puis contrôles NÉGATIFS : chacun décrit
une erreur précise à ne pas commettre.

· un férié ou un week-end compté comme « séance sans échange » — l'erreur
  d'un concurrent sur ATW (« 8 séances sans transaction sur 127 », quand nos
  données en montrent 0 sur 120) ;
· une clôture recopiée (volume nul) prise pour un mouvement ;
· un saut de plus de 10 % (R10) entré dans les rendements ;
· une mesure publiée sur un effectif insuffisant ;
· un titre suspendu, ou en reprise, mesuré comme les autres.

Et une garde de branchement : le bloc ne doit nourrir NI la note, NI le
signal, NI la confiance (R8).
"""
import copy
import math
import re
from datetime import date, timedelta
from pathlib import Path
from statistics import stdev

import pytest

import pipeline.risque as risque
from pipeline.risque import (calendrier_seances, est_jour_ouvre, mesurer_cote,
                             mesurer_risque)

RACINE = Path(__file__).resolve().parent.parent


# ── outils ──────────────────────────────────────────────────────────────────

def jours_ouvres(debut: str, n: int) -> list:
    """n jours ouvrés à partir de `debut`, fériés fixes et week-ends exclus."""
    d, out = date.fromisoformat(debut), []
    while len(out) < n:
        if est_jour_ouvre(d.isoformat()):
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def bougies(dates, closes, volumes=None):
    volumes = volumes or [1000] * len(dates)
    return [{"d": d, "o": c, "h": c, "l": c, "c": c, "v": v}
            for d, c, v in zip(dates, closes, volumes)]


def closes_depuis(rendements, base=100.0):
    out = [base]
    for r in rendements:
        out.append(out[-1] * (1 + r))
    return out


@pytest.fixture
def petit(monkeypatch):
    """Fenêtres réduites, pour des cas qui se calculent à la main."""
    monkeypatch.setattr(risque, "FENETRE_AN", 50)
    monkeypatch.setattr(risque, "FENETRE_LIQUIDITE", 10)
    monkeypatch.setattr(risque, "MIN_RENDEMENTS", 4)
    monkeypatch.setattr(risque, "MIN_SEANCES_LIQUIDITE", 5)


# ── cas calculés à la main ──────────────────────────────────────────────────

def test_volatilite_calculee_a_la_main(petit):
    # +5 %, −5 %, 0, +5 % : moyenne 0,0125 ; écarts² = 0,00140625, 0,00390625,
    # 0,00015625, 0,00140625 ; somme 0,006875 ; ÷3 ; racine 0,0478714 ;
    # × √250 = 0,756919 → 75,69 %.
    cal = jours_ouvres("2025-03-03", 5)
    b = bougies(cal, [100, 105, 99.75, 99.75, 104.7375])
    r = mesurer_risque(b, cal)
    assert r["volatilite"]["valeur"] == 75.69
    assert r["volatilite"]["n"] == 4
    assert (r["volatilite"]["du"], r["volatilite"]["au"]) == (cal[0], cal[-1])
    assert r["motif"] is None


def test_var_et_cvar_sur_quarante_rendements(petit):
    # 40 rendements : queue à 5 % = 2 observations (⌈0,05 × 40⌉ = 2, et non 3
    # comme le donnerait le flottant 0,050000000000000044 × 40 sans arrondi).
    # Les deux pires : −8 % et −6 % → VaR 6,00 ; CVaR (8 + 6) / 2 = 7,00.
    rend = [0.01, -0.01] * 19 + [-0.08, -0.06]
    cal = jours_ouvres("2025-03-03", 41)
    r = mesurer_risque(bougies(cal, closes_depuis(rend)), cal)
    assert r["var95"]["n_queue"] == 2
    assert r["var95"]["valeur"] == 6.0
    assert r["var95"]["cvar"] == 7.0


def test_perte_maximale_avec_dates_du_sommet_et_du_creux(petit):
    # 100 → 105 → 110 (sommet) → 100 → 95 (creux) → 99 → 104 :
    # 1 − 95/110 = 13,636 % → 13,64.
    cal = jours_ouvres("2025-03-03", 7)
    r = mesurer_risque(bougies(cal, [100, 105, 110, 100, 95, 99, 104]), cal)
    pm = r["perte_max"]
    assert pm["valeur"] == 13.64
    assert pm["sommet"] == {"d": cal[2], "c": 110}
    assert pm["creux"] == {"d": cal[4], "c": 95}


def test_beta_deux_et_correlation_un(petit):
    cal = jours_ouvres("2025-03-03", 9)
    m = [0.01, -0.02, 0.015, 0.0, -0.01, 0.02, -0.005, 0.01]
    masi = dict(zip(cal, closes_depuis(m, 10000)))
    titre = closes_depuis([2 * x for x in m])
    r = mesurer_risque(bougies(cal, titre), cal, masi)
    assert r["beta"]["valeur"] == 2.0
    assert r["beta"]["correlation"] == 1.0
    assert r["beta"]["n"] == 8


def test_beta_sur_les_seules_seances_communes_sans_interpolation(petit):
    # Une date absente du MASI retire les DEUX intervalles qui la touchent.
    cal = jours_ouvres("2025-03-03", 9)
    m = [0.01, -0.02, 0.015, 0.0, -0.01, 0.02, -0.005, 0.01]
    masi = dict(zip(cal, closes_depuis(m, 10000)))
    del masi[cal[4]]
    r = mesurer_risque(bougies(cal, closes_depuis([2 * x for x in m])), cal, masi)
    assert r["beta"]["n"] == 6
    assert r["volatilite"]["n"] == 8          # la volatilité, elle, garde tout


def test_liquidite_quantite_mediane_et_montant_absent(petit):
    cal = jours_ouvres("2025-03-03", 10)
    vols = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    r = mesurer_risque(bougies(cal, [100] * 10, vols), cal)
    liq = r["liquidite"]
    assert liq["quantite_mediane"] == 55
    assert liq["seances"] == 10 and liq["sans_echange"] == 0
    assert liq["montant_median"] is None and "quantité" in liq["motif_montant"]
    assert liq["amihud"] is None and "montant" in liq["motif_amihud"]


# ── contrôles négatifs ──────────────────────────────────────────────────────

def test_un_ferie_n_est_pas_une_seance_sans_echange(petit):
    """L'erreur du concurrent : compter un jour calendaire comme une séance."""
    # Fenêtre qui enjambe le 1er mai 2025 (jeudi, férié) et deux week-ends.
    cal = jours_ouvres("2025-04-24", 10)
    assert "2025-05-01" not in cal
    marche = {f"T{i}": bougies(cal, [100] * 10) for i in range(25)}
    assert calendrier_seances(marche) == cal
    r = mesurer_risque(marche["T0"], calendrier_seances(marche))
    assert r["liquidite"]["sans_echange"] == 0
    assert r["liquidite"]["seances"] == 10


def test_un_ferie_du_registre_ne_devient_pas_une_seance_meme_s_il_porte_des_bougies():
    jours = ["2025-04-30", "2025-05-01", "2025-05-02"]
    marche = {f"T{i}": bougies(jours, [100, 100, 100]) for i in range(25)}
    assert calendrier_seances(marche) == ["2025-04-30", "2025-05-02"]


def test_un_week_end_n_est_jamais_une_seance():
    jours = ["2025-03-07", "2025-03-08", "2025-03-10"]     # ven, sam, lun
    marche = {f"T{i}": bougies(jours, [100, 100, 100]) for i in range(25)}
    assert calendrier_seances(marche) == ["2025-03-07", "2025-03-10"]


def test_une_seance_reelle_sans_bougie_est_comptee_et_distinguee(petit):
    cal = jours_ouvres("2025-03-03", 10)
    titre = bougies(cal[:4] + cal[5:], [100] * 9)            # trou le 5e jour
    titre[2]["v"] = 0                                        # et une bougie à 0
    r = mesurer_risque(titre, cal)
    liq = r["liquidite"]
    assert liq["sans_echange"] == 2
    assert liq["dont_volume_nul"] == 1 and liq["dont_sans_bougie"] == 1


def test_une_journee_avec_trop_peu_de_titres_n_est_pas_une_seance():
    jours = ["2025-03-03", "2025-03-04"]
    marche = {f"T{i}": bougies(jours[:1], [100]) for i in range(25)}
    marche.update({f"U{i}": bougies(jours, [100, 100]) for i in range(5)})
    assert calendrier_seances(marche) == ["2025-03-03"]


def test_volume_nul_exclu_des_rendements(petit):
    """Une clôture recopiée n'est pas un mouvement."""
    cal = jours_ouvres("2025-03-03", 6)
    closes = [100, 105, 50, 99.75, 99.75, 104.7375]     # le 50 est une recopie
    vols = [1000, 1000, 0, 1000, 1000, 1000]
    r = mesurer_risque(bougies(cal, closes, vols), cal)
    assert r["rendements"]["exclus_volume_nul"] == 1
    assert r["rendements"]["exclus_saut"] == 0
    # 105 → 99,75 couvre DEUX séances : compté, et écarté depuis le 14/10/2026
    # (une mesure « à 1 jour » ne mélange pas les horizons). Restent 3
    # rendements d'une séance, sous le minimum de 4 : pas de volatilité.
    assert r["rendements"]["sur_plusieurs_seances"] == 1
    assert r["rendements"]["n"] == 3
    assert r["volatilite"]["valeur"] is None


def test_un_rendement_sur_plusieurs_seances_n_entre_pas_dans_la_var(petit):
    cal = jours_ouvres("2025-03-03", 7)
    closes = [100, 101, 102, 50, 96, 97, 98]              # 50 : recopie, volume nul
    vols = [1000, 1000, 1000, 0, 1000, 1000, 1000]
    r = mesurer_risque(bougies(cal, closes, vols), cal)
    assert r["rendements"]["sur_plusieurs_seances"] == 1   # 102 → 96 sur deux séances
    vals = [0.01, 102 / 101 - 1, 97 / 96 - 1, 98 / 97 - 1]
    assert r["rendements"]["n"] == 4
    assert r["volatilite"]["valeur"] == round(100 * stdev(vals) * math.sqrt(250), 2)


def test_saut_de_plus_de_dix_pour_cent_exclu_et_compte(petit):
    cal = jours_ouvres("2025-03-03", 7)
    closes = [100, 105, 99.75, 99.75, 104.7375, 125.685, 125.685]   # +20 %
    r = mesurer_risque(bougies(cal, closes), cal)
    assert r["rendements"]["exclus_saut"] == 1
    assert r["rendements"]["sauts"] == [{"du": cal[4], "au": cal[5], "variation": 20.0}]
    assert r["rendements"]["n"] == 5
    vals = [0.05, -0.05, 0.0, 0.05, 0.0]
    assert r["volatilite"]["valeur"] == round(100 * stdev(vals) * math.sqrt(250), 2)
    # les clôtures de part et d'autre du saut ne sont pas comparables
    assert r["perte_max"]["valeur"] is None and "10 %" in r["perte_max"]["motif"]


def test_le_plafond_de_dix_pour_cent_lui_meme_reste_admis(petit):
    cal = jours_ouvres("2025-03-03", 6)
    closes = [100, 110, 99, 99, 108.9, 108.9]              # ±10 % exactement
    r = mesurer_risque(bougies(cal, closes), cal)
    assert r["rendements"]["exclus_saut"] == 0


def test_effectif_insuffisant_rend_null_avec_motif():
    """Seuil réel : 120 rendements. 119 → null ; 120 → mesuré."""
    cal = jours_ouvres("2025-01-02", 121)
    rend = [0.01, -0.01] * 60
    r119 = mesurer_risque(bougies(cal[1:], closes_depuis(rend[:119])), cal)
    assert r119["volatilite"]["valeur"] is None
    assert r119["var95"]["valeur"] is None and r119["beta"]["valeur"] is None
    assert r119["perte_max"]["valeur"] is None
    assert "119 rendements" in r119["volatilite"]["motif"]
    assert r119["motif"]["code"] in ("effectif_insuffisant", "historique_court")
    r120 = mesurer_risque(bougies(cal, closes_depuis(rend)), cal)
    assert r120["volatilite"]["valeur"] is not None and r120["volatilite"]["n"] == 120


def test_titre_illiquide_effectif_insuffisant_motif_explicite():
    cal = jours_ouvres("2025-01-02", 250)
    marche_un_jour_sur_trois = cal[::3]
    r = mesurer_risque(bougies(marche_un_jour_sur_trois, [100] * len(marche_un_jour_sur_trois)), cal)
    assert r["motif"]["code"] == "effectif_insuffisant"
    assert r["volatilite"]["valeur"] is None


def test_titre_suspendu_null_partout(petit):
    cal = jours_ouvres("2025-03-03", 10)
    susp = {"depuis": "2023-10-03", "motif": "liquidation judiciaire"}
    r = mesurer_risque(bougies(cal, [100] * 10), cal, suspension=susp)
    assert r["motif"]["code"] == "suspendu"
    for cle in ("volatilite", "beta", "perte_max", "var95", "liquidite"):
        assert r[cle]["valeur"] is None and "suspendu" in r[cle]["motif"]


def test_titre_suspendu_du_registre_null_via_mesurer_cote():
    cal = jours_ouvres("2025-01-02", 260)
    series = {f"T{i}": bougies(cal, closes_depuis([0.01, -0.01] * 130)[:260]) for i in range(25)}
    series["DIS"] = bougies(cal, [26.25] * 260, [0] * 260)
    out = mesurer_cote(series, None, ["DIS", "T0"])
    assert out["DIS"]["motif"]["code"] == "suspendu"
    assert out["T0"]["volatilite"]["valeur"] is not None


def test_reprise_de_cotation_recommence_la_fenetre(petit):
    # Avant la reprise : un régime à 4 500 ; après : 2 400. Le saut de −47 %
    # ne doit ni entrer dans les rendements ni être compté comme un « saut
    # non expliqué » : la reprise est au registre (R11).
    cal = jours_ouvres("2025-03-03", 12)
    closes = [4500, 4510, 4490, 4500, 4505, 4500, 2400, 2410, 2400, 2420, 2410, 2400]
    r = mesurer_risque(bougies(cal, closes), cal, reprise=cal[6])
    assert r["rendements"]["exclus_saut"] == 0
    assert r["rendements"]["du"] == cal[6]
    assert r["volatilite"]["n"] == 5
    r_court = mesurer_risque(bougies(cal, closes), cal, reprise=cal[9])
    assert r_court["motif"]["code"] == "reprise_trop_recente"
    assert r_court["volatilite"]["valeur"] is None
    assert r_court["liquidite"]["valeur"] is None


def test_la_seance_en_cours_est_exclue_par_jusqu_au(petit):
    cal = jours_ouvres("2025-03-03", 8)
    b = bougies(cal, [100, 105, 99.75, 99.75, 104.7375, 104.7375, 104.7375, 150])
    r = mesurer_risque(b, cal, jusqu_au=cal[-2])
    assert r["asof"] == cal[-2] and r["rendements"]["exclus_saut"] == 0


def test_fonction_pure_entrees_intactes(petit):
    cal = jours_ouvres("2025-03-03", 10)
    b = bougies(cal, [100, 101, 102, 101, 100, 99, 100, 101, 102, 103])
    masi = dict(zip(cal, [1000 + i for i in range(10)]))
    avant = copy.deepcopy((b, cal, masi))
    r1 = mesurer_risque(b, cal, masi)
    r2 = mesurer_risque(b, cal, masi)
    assert (b, cal, masi) == avant and r1 == r2


# ── branchement : hors note (R8) ────────────────────────────────────────────

def test_le_bloc_risque_ne_nourrit_ni_la_note_ni_le_signal_ni_la_confiance():
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    # Le seul usage du bloc dans le moteur est son affectation.
    usages = [m.start() for m in re.finditer(r"""\[["']risque["']\]""", src)]
    assert len(usages) == 1, "le bloc `risque` est lu ailleurs dans le moteur"
    affectation = src.index('x["risque"] = _risques.get(x["symbol"])')
    # … et il est calculé APRÈS la note par famille, qui fixe note et signal.
    assert src.index("note_metier_du_run(tickers_out, passe1") < affectation
    for fichier in ("pipeline/coherence.py", "pipeline/score_history.py"):
        p = RACINE / fichier
        if p.exists():
            assert "risque" not in re.sub(r"#.*", "", p.read_text(encoding="utf-8"))


def test_le_terminal_recoit_le_bloc():
    """Le chemin de données, pas seulement le composant (cf. rang_secteur)."""
    src = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    assert "risque:t.risque" in src
    assert "Risque mesuré" in src
