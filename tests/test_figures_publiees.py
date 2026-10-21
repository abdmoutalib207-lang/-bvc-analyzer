"""Figures publiées : des faits datés, jamais de prévision, jamais de futur.

Quatre familles :
  1. cas jouets, attendus calculés À LA MAIN (pivots, double creux, gap,
     rupture, séance à volume nul) ;
  2. équivalence : les figures DÉCLENCHÉES de `figures_detail` sont exactement
     les signaux de `figures()` / `lignes()` du banc d'essai du 03/10/2026 —
     preuve qu'aucun paramètre n'a bougé ;
  3. propriétés sur les données : aucun regard vers le futur, aucune rupture
     traversée, aucune séance à volume nul ;
  4. le fichier publié : format, règle des 30 cas, recalcul.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import bvc_config as cfg  # noqa: E402
import calibrage_gaps as cg  # noqa: E402
import figures_publiees as fp  # noqa: E402
from technical.figures import figures, pivots  # noqa: E402
from technical.figures_detail import figures_detail, gaps_detail, lignes_detail  # noqa: E402
from technical.lignes import lignes  # noqa: E402
from technical.serie_propre import charger, evenements_titre, ruptures  # noqa: E402

PUBLIE = RACINE / "datasets" / "figures_publiees.json"
CANDLES = RACINE / "pipeline" / "candles"


@pytest.fixture(scope="module")
def pub():
    return json.loads(PUBLIE.read_text(encoding="utf-8"),
                      parse_constant=lambda x: pytest.fail(f"constante non JSON : {x}"))


def _serie_double_creux():
    """100 → 80 (idx 20) → 100 (idx 40) → 80,4 (idx 60) → +1 %/séance.

    À LA MAIN : le second creux (80,4) est confirmé à la première clôture
    ≥ 80,4 × 1,06 = 85,224, soit 80,4 × 1,01^6 = 85,34 → idx 66.
    """
    d1 = np.linspace(100, 80, 21)
    d2 = np.linspace(80, 100, 21)[1:]
    d3 = np.linspace(100, 80.4, 21)[1:]
    up = 80.4 * 1.01 ** np.arange(1, 12)
    return np.concatenate([d1, d2, d3, up])


# ── 1. cas jouets ────────────────────────────────────────────────────────

def test_pivots_a_la_main():
    c = _serie_double_creux()
    p = pivots(c)
    assert [(i, t, cf) for i, _, t, cf in p][-2:] == [(40, "H", 47), (60, "L", 66)]
    assert p[-1][1] == pytest.approx(80.4)


def test_pas_de_regard_vers_le_futur_double_creux():
    """Absente la veille de la confirmation du dernier pivot, présente le jour même."""
    c = _serie_double_creux()
    avant = [f["type"] for f in figures_detail(c[:66])]      # séances 0..65
    apres = [f for f in figures_detail(c[:67]) if f["type"] == "double_creux"]   # 0..66
    assert "double_creux" not in avant
    assert len(apres) == 1
    f = apres[0]
    assert f["conf"] == 66 and f["statut"] == "armee"
    assert f["niveau"] == {"forme": "horizontal", "prix": pytest.approx(100.0)}
    assert [(i, t) for i, _, t, _ in f["pivots"]] == [(20, "L"), (40, "H"), (60, "L")]


def test_double_creux_declenche_a_la_premiere_cloture_au_dessus_du_cou():
    c = np.concatenate([_serie_double_creux(), [95.0, 100.0, 101.0, 90.0]])
    f = [x for x in figures_detail(c) if x["type"] == "double_creux"][0]
    # 100,0 n'est pas > 100 ; la cassure est la clôture à 101 (idx 74), pas la suivante
    assert f["statut"] == "declenchee" and f["i_fin"] == 74
    assert (f["i_fin"], f["signal"], f["sens"]) == (74, "double_creux", +1)


def test_statut_invalide_si_le_cours_passe_sous_le_creux():
    # invalidation : sous min(80 ; 80,4) × 0,97 = 77,6
    c = np.concatenate([_serie_double_creux(), [80.0, 77.0]])
    f = [x for x in figures_detail(c) if x["type"] == "double_creux"][0]
    assert f["statut"] == "invalidee" and f["i_fin"] == 73


def test_gap_a_la_main():
    # veille : plus haut 101. Jour du gap : plus bas 103 ≥ 101 × 1,01 → zone [101 ; 103].
    o = np.array([100., 103., 104., 103.])
    h = np.array([101., 105., 105., 104.])
    l = np.array([99., 103., 102., 100.5])
    c = np.array([100., 104., 103., 101.])
    (g,) = gaps_detail(o, h, l, c)
    assert (g["t"], g["sens"], g["bas"], g["haut"]) == (1, +1, 101.0, 103.0)
    assert g["i_touche"] == 2          # l = 102 ≤ 103 : revient dans la zone
    assert g["i_comble"] == 3          # l = 100,5 ≤ 101 : la traverse entièrement


def test_gap_ouvert_tant_que_la_zone_n_est_pas_traversee():
    o = np.array([100., 103., 104.])
    h = np.array([101., 105., 106.])
    l = np.array([99., 103., 104.])
    c = np.array([100., 104., 105.])
    (g,) = gaps_detail(o, h, l, c)
    assert g["i_touche"] is None and g["i_comble"] is None


def test_ecart_de_plus_de_10_pour_cent_n_est_jamais_un_gap():
    """Veille 100 → 116 : au-delà du plafond de ±10 % (R10), c'est une série cassée."""
    o = np.array([100., 118.])
    h = np.array([101., 120.])
    l = np.array([99., 116.])
    c = np.array([100., 119.])
    assert gaps_detail(o, h, l, c) == []
    assert ruptures(["2026-01-05", "2026-01-06"], c, []) == {1}


def test_gap_jamais_a_travers_une_operation_declaree():
    """Split déclaré entre deux séances : le « gap » de 3 % qui les sépare est écarté."""
    o = np.array([100., 103.])
    h = np.array([101., 105.])
    l = np.array([99., 103.])
    c = np.array([100., 104.])
    dates = ["2026-07-24", "2026-07-27"]
    rup = ruptures(dates, c, ["2026-07-27"])
    assert rup == {1}
    assert gaps_detail(o, h, l, c, frozenset(rup)) == []
    assert len(gaps_detail(o, h, l, c)) == 1        # sans le registre, il serait publié


def test_registre_des_cas_temoins():
    assert evenements_titre("MNG") == ["2026-07-27"]
    assert "2026-09-16" in evenements_titre("CMT") and "2026-07-17" in evenements_titre("CMT")


def test_seance_a_volume_nul_n_entre_pas(tmp_path):
    """Une bougie plate à 110 sans volume ne fabrique ni gap haussier ni baissier."""
    bougies = [
        {"d": "2026-01-05", "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 10},
        {"d": "2026-01-06", "o": 110.0, "h": 110.0, "l": 110.0, "c": 110.0, "v": 0},
        {"d": "2026-01-07", "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 10},
    ]
    p = tmp_path / "XXX.json"
    p.write_text(json.dumps(bougies), encoding="utf-8")
    s = charger(p)
    assert s["d"] == ["2026-01-05", "2026-01-07"]
    assert gaps_detail(s["o"], s["h"], s["l"], s["c"]) == []
    # contre-épreuve : si la bougie à volume nul entrait, un gap apparaîtrait
    o, h, l, c = (np.array([x[k] for x in bougies]) for k in ("o", "h", "l", "c"))
    assert len(gaps_detail(o, h, l, c)) == 0     # (plate : écartée par `reel`)
    bougies[1].update(o=111.0, h=112.0, l=110.0, c=111.0)
    o, h, l, c = (np.array([x[k] for x in bougies]) for k in ("o", "h", "l", "c"))
    assert len(gaps_detail(o, h, l, c)) >= 1


def test_volume_nul_ou_absent_est_exclu(tmp_path):
    bougies = [{"d": "2026-01-05", "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": None},
               {"d": "2026-01-06", "o": 1.0, "h": 1.1, "l": 1.0, "c": 1.1, "v": 5}]
    p = tmp_path / "XXX.json"
    p.write_text(json.dumps(bougies), encoding="utf-8")
    assert charger(p)["d"] == ["2026-01-06"]


# ── 2. équivalence avec les détecteurs du banc d'essai ──────────────────

def _titres_candles():
    return [p for p in sorted(CANDLES.glob("*.json")) if p.stem in cfg.TICKERS_ALL]


def test_les_figures_declenchees_sont_exactement_les_signaux_du_banc_d_essai():
    verifies = 0
    for p in _titres_candles():
        s = charger(p)
        if s is None or len(s["c"]) < 80:
            continue
        c = s["c"]
        attendu = sorted(figures(c) + lignes(c))
        obtenu = sorted((x["i_fin"], x["signal"], x["sens"])
                        for x in figures_detail(c) + lignes_detail(c) if x["statut"] == "declenchee")
        assert obtenu == [tuple(a) for a in attendu], p.stem
        verifies += 1
    assert verifies >= 70


# ── 3. propriétés sur les données ───────────────────────────────────────

def test_aucun_regard_vers_le_futur_sur_les_donnees_reelles():
    """Tronquer la série à t ne change pas l'ensemble des figures confirmées ≤ t."""
    def cle(f):
        return (f["type"], tuple((i, round(float(p), 6), t, cf) for i, p, t, cf in f["pivots"]), f["conf"])
    for t_ in ("ADH", "IAM", "CIH", "MNG", "SBS"):
        c = charger(CANDLES / f"{t_}.json")["c"]
        complet = figures_detail(c)
        for coupe in (len(c) // 3, len(c) // 2, len(c) - 30, len(c) - 5):
            tronque = {cle(f) for f in figures_detail(c[:coupe])}
            assert all(f["conf"] < coupe for f in figures_detail(c[:coupe]))
            attendu = {cle(f) for f in complet if f["conf"] < coupe}
            assert tronque == attendu, (t_, coupe)


def test_les_ruptures_sont_detectees_et_le_registre_consulte():
    s = charger(CANDLES / "CMT.json")
    rup = ruptures(s["d"], s["c"], evenements_titre("CMT"))
    assert s["d"].index("2026-09-16") in rup
    m = charger(CANDLES / "MNG.json")
    rm = ruptures(m["d"], m["c"], evenements_titre("MNG"))
    assert m["d"].index("2026-07-27") in rm      # déclarée, même si la série est ajustée


# ── 4. le fichier publié ────────────────────────────────────────────────

def test_format_du_fichier(pub):
    assert set(pub["titres"]) == set(cfg.TICKERS_ALL) and len(pub["titres"]) == 80
    for cle in ("_quoi", "_r8", "methode", "frequences", "titres", "derniere_seance_du_marche"):
        assert cle in pub
    statuts_fig = {"armee", "declenchee", "invalidee", "expiree"}
    for t, v in pub["titres"].items():
        assert v["statut_titre"] in {"analyse", "inactif", "historique_insuffisant"}, t
        for f in v["figures"]:
            assert f["statut"] in statuts_fig and f["libelle"]
            assert len(f["pivots"]) >= 3
            dates = [p["date"] for p in f["pivots"]]
            assert dates == sorted(dates)
            assert f["date_confirmation"] >= dates[-1]
            assert f["date_confirmation"] == max(p["date_confirmation"] for p in f["pivots"])
            assert f["frequence_ref"] and all(r in pub["frequences"] for r in f["frequence_ref"])
            assert (f["date_cassure"] is not None) == (f["statut"] == "declenchee"
                                                       and not f["type"].startswith("fibo_"))
            assert not any(k in f for k in ("objectif", "cible", "target"))
        for f in v["lignes"]:
            assert f["statut"] in {"armee", "declenchee"} and len(f["points"]) == 2
            assert all(r in pub["frequences"] for r in f["frequence_ref"])
            if f["type"] == "canal_haussier":
                assert len(f["parallele"]["points"]) == 2
        for g in v["gaps"]:
            assert g["statut"] in {"ouvert", "partiellement_comble", "comble"}
            assert g["zone_haute"] > g["zone_basse"]
            assert (g["date_comblement"] is not None) == (g["statut"] == "comble")
            if g["date_comblement"]:
                assert g["date_comblement"] > g["date"]


def _parcourir(x, chemin=""):
    if isinstance(x, dict):
        yield chemin, x
        for k, v in x.items():
            yield from _parcourir(v, f"{chemin}/{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _parcourir(v, f"{chemin}[{i}]")


def test_aucune_frequence_publiee_sous_30_cas(pub):
    vus = 0
    for chemin, d in _parcourir(pub["frequences"]):
        if "n" in d and "statut" in d:
            vus += 1
            if d["n"] < 30:
                assert d["statut"] == "echantillon_insuffisant", chemin
                assert set(d) - {"periodes", "reproductible_sur_deux_periodes"} <= {"n", "statut"}, f"pourcentage sous 30 cas : {chemin}"
            else:
                assert d["statut"] == "publie", chemin
        if d.get("statut") == "publie":
            assert d["n"] >= 30, chemin
    assert vus > 100


def test_effectifs_et_part_agreges_a_la_main(pub):
    """double_creux, tous, h20 — artefact : (n=30 ; 50,0 %) + (n=59 ; 49,2 %).

    k = 0,500 × 30 = 15 ; 0,492 × 59 = 29,03 → 29. Total 44 / 89 = 49,4 %.
    """
    u = pub["frequences"]["double_creux"]["univers"]["tous"]
    assert u["n"] == 89 and u["part_bon_sens_brute_pct"] == 49.4
    assert u["alpha_median_pct"] is None and u["raison_alpha_median"]
    p2 = u["periodes"]["2025-01_2026-10"]
    assert p2["n"] == 59 and p2["alpha_median_net_frais_pct"] is None and p2["raison_alpha_net"]


def test_signal_a_peu_de_cas_reste_insuffisant(pub):
    # ete_inversee : 7 + 20 = 27 cas « tous » dans l'artefact
    u = pub["frequences"]["ete_inversee"]["univers"]["tous"]
    assert u == {"n": 27, "periodes": {
        "2023-10_2024-12": {"n": 7, "statut": "echantillon_insuffisant"},
        "2025-01_2026-10": {"n": 20, "statut": "echantillon_insuffisant"}},
        "statut": "echantillon_insuffisant"}


def test_aucun_element_ne_traverse_une_operation_sur_titres(pub):
    controles = 0
    for t, v in pub["titres"].items():
        ev = evenements_titre(t)
        derniere = v.get("derniere_seance_echangee")
        for f in v["figures"] + v["lignes"]:
            debut = f["pivots"][0]["date"] if "pivots" in f else f["points"][0]["date"]
            fin = (f.get("date_cassure") or f.get("date_fin") or f.get("date_constat")
                   or derniere)
            assert not any(debut < e <= fin for e in ev), (t, f["type"], debut, fin, ev)
            controles += 1
        for g in v["gaps"]:
            s = charger(CANDLES / f"{t}.json")
            i = s["d"].index(g["date"])
            assert not any(s["d"][i - 1] < e <= g["date"] for e in ev), (t, g)
            assert abs(s["c"][i] / s["c"][i - 1] - 1) <= 0.10, (t, g)
            controles += 1
    assert controles > 100


def test_cas_temoins_mng_et_cmt(pub):
    """Aucune figure de MNG ou CMT ne s'étend de part et d'autre du 27/07 ou de l'OPA."""
    for t, limites in (("MNG", ["2026-07-27"]), ("CMT", ["2026-07-17", "2026-09-16"])):
        v = pub["titres"][t]
        for f in v["figures"] + v["lignes"]:
            debut = f["pivots"][0]["date"] if "pivots" in f else f["points"][0]["date"]
            assert all(debut >= e for e in limites) or all(
                (f.get("date_cassure") or f.get("date_fin") or f.get("date_constat")
                 or v["derniere_seance_echangee"]) < e
                for e in limites)
        for g in v["gaps"]:
            assert g["date"] >= max(limites)


def test_aucune_seance_a_volume_nul_dans_le_publie(pub):
    """Chaque pivot, chaque gap, chaque point de droite tombe sur une séance échangée."""
    verifies = 0
    for t, v in pub["titres"].items():
        if not (v["figures"] or v["lignes"] or v["gaps"]):
            continue
        vol = {b["d"]: (b.get("v") or 0)
               for b in json.loads((CANDLES / f"{t}.json").read_text(encoding="utf-8"))}
        dates = []
        for f in v["figures"]:
            dates += [p["date"] for p in f["pivots"]] + [p["date_confirmation"] for p in f["pivots"]]
        for f in v["lignes"]:
            dates += [p["date"] for p in f["points"]]
        dates += [g["date"] for g in v["gaps"]]
        for d in dates:
            assert vol[d] > 0, (t, d)
            verifies += 1
    assert verifies > 300


def test_le_fichier_publie_se_recalcule(pub):
    """Rejouer sur les chandelles arrêtées à sa dernière séance redonne le même fichier.

    Famille « données publiées » : si les chandelles ont changé depuis la
    génération (un run intrajournalier les a réécrites, le moteur n'a pas encore
    regénéré le fichier), l'empreinte diffère et le test le DIT au lieu
    d'échouer — ce n'est pas un défaut du code.
    """
    fin = pub["derniere_seance_du_marche"]
    if fp.empreinte(RACINE, fin) != pub["entree_sha256"]:
        pytest.skip("chandelles modifiées depuis la génération de figures_publiees.json : "
                    "relancer pipeline/figures_publiees.py")
    res = fp.construire(RACINE, fin)
    assert json.loads(json.dumps(res, ensure_ascii=False)) == pub


def test_gaps_comblement_se_recalcule():
    """L'artefact de comblement est arrêté au 02/10/2026 : stable d'une séance à l'autre."""
    artefact = json.loads((RACINE / fp.ARTEFACT_GAPS).read_text(encoding="utf-8"))
    assert json.loads(json.dumps(cg.mesurer(), ensure_ascii=False)) == artefact


def test_sortie_deterministe_sans_horloge():
    a = json.dumps(fp.construire(RACINE, "2026-10-02"), ensure_ascii=False)
    b = json.dumps(fp.construire(RACINE, "2026-10-02"), ensure_ascii=False)
    assert a == b


# ── lisibilité des conditions d'usage (revue du 21/10) ───────────────────

def test_frais_dits_en_clair(pub):
    assert "brutes de frais (2 % d'aller-retour non déduits)" in pub["_avertissement"]
    for chemin, d in _parcourir(pub["frequences"]):
        assert "part_bon_sens_pct" not in d, chemin          # le champ s'appelle _brute_
        assert "sens_attendu" not in d, chemin               # renommé sens_teste
    assert pub["frequences"]["double_creux"]["sens_teste"] == +1


def test_figure_armee_porte_sa_condition_d_usage(pub):
    armees = [x for v in pub["titres"].values() for x in v["figures"] + v["lignes"]
              if x["statut"] == "armee"]
    assert len(armees) > 0
    assert all(x["frequence_condition"] == "apres_cassure" for x in armees)
    autres = [x for v in pub["titres"].values() for x in v["figures"] + v["lignes"]
              if x["statut"] != "armee"]
    assert all("frequence_condition" not in x for x in autres)


def test_gap_publie_son_age_et_se_mesure_depuis_la_seance_du_gap(pub):
    assert "depuis la séance du gap" in pub["frequences"]["gap_haussier"]["mesure"]
    gaps = [g for v in pub["titres"].values() for g in v["gaps"]]
    assert gaps and all(isinstance(g["age_seances"], int) and g["age_seances"] >= 0
                        for g in gaps)


def test_frequences_et_ruptures_dit_ce_qui_a_ete_mesure(pub):
    m = pub["methode"]["frequences_et_ruptures"]
    mesure = json.loads((RACINE / fp.ARTEFACT_RUPTURES).read_text(encoding="utf-8"))
    assert m["evenements"] == mesure["evenements_publies_signaux"]
    assert m["traversant_une_rupture"] == mesure["evenements_traversant_une_rupture"]
    # 8 / 1 229 = 0,65 % (< 1 %) mais le plus grand écart de part est 1,1 point (> 0,5) :
    # la règle « moins de 1 % ET aucun écart > 0,5 point » n'est PAS satisfaite.
    assert (m["traversant_une_rupture"], m["evenements"]) == (8, 1229)
    assert m["pct_traversant"] == 0.65 and m["plus_grand_ecart_part_points"] == 1.1
    assert m["negligeable"] is False and m["filtre_applique_aux_frequences"] is False
    assert "ne porte PAS sur les fréquences publiées" in m["texte"]


def test_ecart_de_1299_a_1286_vient_du_fichier_tgc():
    """76 titres de TICKERS_ALL avec ≥ 80 séances échangées → 1 286 signaux ;
    le fichier TGC (alias, hors TICKERS_ALL) en ajoute 13, d'où 1 299 sur 77 fichiers."""
    assert {p.stem for p in CANDLES.glob("*.json")} - set(cfg.TICKERS_ALL) == {"TGC"}
