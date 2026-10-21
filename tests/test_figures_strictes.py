"""Figures strictes (21/10/2026) : des règles qui ne font que REJETER.

Cinq familles :
  1. cas construits À LA MAIN, un par règle : ETE asymétrique, ligne de cou
     trop inclinée, triangle non confiné, oblique traversée, oblique à deux
     contacts — chacun accepté par l'ancien jeu (2026-10-03), rejeté par le
     nouveau, avec son contre-exemple accepté par les deux ;
  2. bornes des prédicats (rapport 0,5 / 2, cou ±5 %, 2 clôtures hors des droites) ;
  3. l'ancien comportement est INTACT : `figures(regles="2026-10-03")` égale la
     fonction archivée `figures_v1`, sur les 80 titres ;
  4. publication et calibrage restent identiques sous les DEUX jeux de règles, et
     le nouveau jeu est un sous-ensemble de l'ancien ;
  5. le volume est une information, jamais un filtre.

⚠️ Ces règles ont été écrites AVANT la mesure et ne sont pas réglées sur ADI ni
sur ADH (décision d'Abd Moutalib, 21/10/2026).
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import bvc_config as cfg  # noqa: E402
import figures_publiees as fp  # noqa: E402
from technical import regles_strictes as rs  # noqa: E402
from technical.figures import figures, figures_v1  # noqa: E402
from technical.figures_detail import figures_detail, lignes_detail  # noqa: E402
from technical.lignes import lignes, lignes_v1  # noqa: E402
from technical.serie_propre import charger  # noqa: E402

V1, V2 = rs.REGLES_V1, rs.REGLES_V2
CANDLES = RACINE / "pipeline" / "candles"
PUBLIE = RACINE / "datasets" / "figures_publiees.json"


def serie(pts):
    """Clôtures linéaires par morceaux entre des points (indice, prix)."""
    return np.interp(np.arange(pts[-1][0] + 1), [p[0] for p in pts], [p[1] for p in pts])


def noms(sig):
    return sorted(n for _, n, _ in sig)


# ── 1. cas construits à la main ─────────────────────────────────────────
# Pivots à 6 % : tous les points ci-dessous sont des retournements de 10 % au moins.

ETE_SYM = serie([(0, 90), (10, 100), (30, 90), (50, 110), (70, 90), (90, 100), (100, 85)])
# épaule gauche 10, tête 50, épaule droite 90 : 40 séances de part et d'autre → rapport 1 ;
# cou 90 / 90 → 0 %.


def test_ete_symetrique_accepte_par_les_deux_jeux():
    assert "ete" in noms(figures(ETE_SYM, regles=V1))
    assert "ete" in noms(figures(ETE_SYM, regles=V2))


def test_ete_asymetrique_rejetee():
    # épaule 10, tête 70, épaule 90 : 60 séances puis 20 → rapport 3 > 2
    c = serie([(0, 90), (10, 100), (40, 90), (70, 110), (80, 90), (90, 100), (100, 85)])
    assert (70 - 10) / (90 - 70) == 3
    assert "ete" in noms(figures(c, regles=V1))          # l'ancien jeu la reconnaissait
    assert "ete" not in noms(figures(c, regles=V2))
    assert "ete" not in [f["type"] for f in figures_detail(c, regles=V2)]


def test_ligne_de_cou_trop_inclinee_rejetee():
    # creux de cou 90 puis 80 : T2/T1 − 1 = −11,1 % ; durées symétriques (rapport 1)
    c = serie([(0, 90), (10, 100), (30, 90), (50, 110), (70, 80), (90, 100), (100, 85), (110, 60)])
    assert abs(80 / 90 - 1) > 0.05 and (50 - 10) / (90 - 50) == 1
    assert "ete" in noms(figures(c, regles=V1))
    assert "ete" not in noms(figures(c, regles=V2))


def _triangles(c, regles):
    return {(f["type"], f["pivots"][0][0]) for f in figures_detail(c, regles=regles)
            if f["type"].startswith("triangle")}


TRI = serie([(0, 130), (30, 100), (50, 110), (70, 100), (76, 106.5), (90, 98)])
# pivots : H0 130, L30 100, H50 110, L70 100, H76 106,5.
# Triangle A (H0 L30 H50 L70) : droite haute par (0;130)-(50;110), pente −0,4 ; après le creux
#   de la séance 70 le cours remonte jusqu'à 106,5 (séance 76, confirmation du creux) : la droite
#   vaut 100,8 / 100,4 / 100,0 / 99,6 aux séances 73 à 76 (×1,01 : 101,8 … 100,6) alors que les
#   clôtures valent 103,3 / 104,3 / 105,4 / 106,5 → 4 clôtures hors des droites, plus de 2.
# Triangle B (L30 H50 L70 H76) : droite haute par (50;110)-(76;106,5), quasi plate : confiné.


def test_triangle_non_confine_rejete_et_triangle_confine_conserve():
    v1, v2 = _triangles(TRI, V1), _triangles(TRI, V2)
    assert ("triangle_descendant", 0) in v1       # A : accepté par l'ancien jeu
    assert ("triangle_descendant", 0) not in v2   # A : rejeté, plus de 2 clôtures hors des droites
    assert ("triangle_descendant", 30) in v1 and ("triangle_descendant", 30) in v2   # B : confiné


def test_triangle_bornes_du_confinement():
    # 2 clôtures dehors : accepté ; 3 : rejeté. Droites horizontales 110 / 100, tolérance 1 %.
    hauts = [(0, 110.0), (20, 110.0)]
    bas = [(10, 100.0), (30, 100.0)]
    c = np.full(31, 105.0)
    c[5] = 112.0
    c[6] = 112.0
    assert 112.0 > 110 * 1.01 and rs.triangle_confine(c, hauts, bas, 0, 30)         # 2 dehors
    c[7] = 112.0
    assert not rs.triangle_confine(c, hauts, bas, 0, 30)                              # 3 dehors
    c = np.full(31, 105.0)
    c[5] = 110.9          # 0,82 % au-dessus de la droite : dans la tolérance de 1 %
    c[6] = 110.9
    c[7] = 110.9
    assert rs.triangle_confine(c, hauts, bas, 0, 30)


OBL_3 = serie([(0, 110), (10, 120), (30, 100), (50, 110), (70, 88), (90, 100), (98, 93), (112, 102)])
# sommets 120 (séance 10), 110 (50), 100 (90) : alignés sur une droite de pente −0,25 ;
# la droite (50 ; 110)-(90 ; 100) a pour contact supplémentaire le sommet de la séance 10.


def test_oblique_a_trois_contacts_acceptee():
    assert "oblique_baissiere_cassee" in noms(lignes(OBL_3, regles=V1))
    assert "oblique_baissiere_cassee" in noms(lignes(OBL_3, regles=V2))


def test_oblique_a_deux_contacts_seulement_rejetee():
    # le sommet de la séance 10 vaut 105 au lieu de 120 : à 12,5 % de la droite → 2 contacts
    c = serie([(0, 100), (10, 105), (30, 100), (50, 110), (70, 88), (90, 100), (98, 93), (112, 102)])
    assert abs(105 / 120 - 1) > rs.CONTACT_TOL
    assert "oblique_baissiere_cassee" in noms(lignes(c, regles=V1))
    assert "oblique_baissiere_cassee" not in noms(lignes(c, regles=V2))


def test_oblique_traversee_par_une_cloture_rejetee():
    # le cours reste à 120 de la séance 10 à la séance 22 : la droite descend à 117 → les clôtures
    # des séances 11 à 22 sont à plus de 1 % AU-DESSUS de la résistance, entre deux contacts
    c = serie([(0, 110), (10, 120), (22, 120), (30, 100), (50, 110), (70, 88), (90, 100), (98, 93), (112, 102)])
    f = lambda i: 120 - 0.25 * (i - 10)
    assert c[22] > f(22) * 1.01          # 120 > 117 × 1,01
    assert "oblique_baissiere_cassee" in noms(lignes(c, regles=V1))
    assert "oblique_baissiere_cassee" not in noms(lignes(c, regles=V2))


def test_canal_dont_le_support_n_a_que_deux_contacts_rejete():
    # deux creux montants (60 puis 70, séances 20 et 60), un sommet de 100 entre eux ; le support
    # (pente +0,25) est cassé par le bas après la séance 66 (clôture < support × 0,98)
    c = serie([(0, 80), (20, 60), (40, 100), (60, 70), (66, 75), (90, 62)])
    sig1, sig2 = noms(lignes(c, regles=V1)), noms(lignes(c, regles=V2))
    assert any(n.startswith("canal") for n in sig1)
    assert not any(n.startswith("canal") for n in sig2)


# ── 2. bornes des prédicats ─────────────────────────────────────────────

def test_ete_ok_bornes():
    assert rs.ete_ok(0, 20, 60, 100, 100)          # 20 / 40 = 0,5 : borne incluse
    assert rs.ete_ok(0, 40, 60, 100, 100)          # 40 / 20 = 2 : borne incluse
    assert not rs.ete_ok(0, 41, 60, 100, 100)      # 41 / 19 > 2
    assert not rs.ete_ok(0, 19, 60, 100, 100)      # 19 / 41 < 0,5
    assert rs.ete_ok(0, 30, 60, 100, 104.9)        # cou à +4,9 %
    assert not rs.ete_ok(0, 30, 60, 100, 105.1)    # cou à +5,1 %
    assert not rs.ete_ok(0, 30, 60, 100, 94.9)     # cou à −5,1 %


def test_droite_validee_bornes():
    # résistance descendante par (50 ; 110) et (90 ; 100), contact supplémentaire (10 ; 120)
    c = np.full(100, 90.0)
    a, b = (50, 110.0), (90, 100.0)
    assert rs.droite_validee(c, a, b, [(10, 120.0, "H", 20)], +1)
    assert rs.droite_validee(c, a, b, [(10, 121.1, "H", 20)], +1)         # 0,92 % de la droite
    assert not rs.droite_validee(c, a, b, [(10, 121.3, "H", 20)], +1)     # 1,08 % : plus un contact
    assert not rs.droite_validee(c, a, b, [], +1)                          # aucun contact de plus
    c2 = c.copy()
    c2[30] = 115 * 1.0099                                                  # 0,99 % au-dessus (f(30)=115)
    assert rs.droite_validee(c2, a, b, [(10, 120.0, "H", 20)], +1)
    c2[30] = 115 * 1.0101
    assert not rs.droite_validee(c2, a, b, [(10, 120.0, "H", 20)], +1)     # 1,01 % : rejeté
    # un support se juge de l'autre côté : une clôture AU-DESSUS ne le gêne pas
    sup_a, sup_b = (50, 100.0), (90, 110.0)
    cs_ = np.full(100, 150.0)
    assert rs.droite_validee(cs_, sup_a, sup_b, [(10, 90.0, "L", 20)], -1)
    cs_[30] = 89.0            # f(30) = 95 : 6 % sous le support
    assert not rs.droite_validee(cs_, sup_a, sup_b, [(10, 90.0, "L", 20)], -1)


def test_jeu_de_regles_inconnu_refuse():
    c = np.linspace(100, 120, 120)
    with pytest.raises(ValueError):
        figures(c, regles="2026-01-01")
    with pytest.raises(ValueError):
        lignes(c, regles="2026-01-01")
    assert rs.REGLES == V2                      # le défaut est le jeu le plus récent


# ── 3. l'ancien comportement est intact ─────────────────────────────────

def _series_reelles():
    for p in sorted(CANDLES.glob("*.json")):
        if p.stem in cfg.TICKERS_ALL:
            s = charger(p)
            if s is not None and len(s["c"]) >= 80:
                yield p.stem, s


def test_ancien_jeu_identique_a_la_fonction_archivee():
    vus = 0
    for t, s in _series_reelles():
        c = s["c"]
        assert figures(c, regles=V1) == figures_v1(c), t
        assert lignes(c, regles=V1) == lignes_v1(c), t
        assert figures(c, 0.10, 12, regles=V1) == figures_v1(c, 0.10, 12), t     # hebdomadaire
        vus += 1
    assert vus >= 70


# ── 4. publication = calibrage, et le nouveau jeu ne fait que rejeter ───

@pytest.mark.parametrize("regles", [V1, V2])
def test_publication_et_calibrage_identiques(regles):
    for t, s in _series_reelles():
        c = s["c"]
        attendu = sorted(figures(c, regles=regles) + lignes(c, regles=regles))
        obtenu = sorted((x["i_fin"], x["signal"], x["sens"])
                        for x in figures_detail(c, regles=regles) + lignes_detail(c, regles=regles)
                        if x["statut"] == "declenchee")
        assert obtenu == [tuple(a) for a in attendu], (t, regles)


def test_le_nouveau_jeu_est_un_sous_ensemble_de_l_ancien():
    perdus = Counter()
    for t, s in _series_reelles():
        c = s["c"]
        for kind, f in (("fig", figures), ("lig", lignes)):
            anc, nou = Counter(f(c, regles=V1)), Counter(f(c, regles=V2))
            assert not (nou - anc), (t, kind)             # rien de nouveau n'apparaît
            perdus.update(n for (_, n, _), k in (anc - nou).items() for _ in range(k))
    # les règles rejettent bel et bien quelque chose, là où elles s'appliquent
    assert perdus["oblique_baissiere_cassee"] > 0 and perdus["ete"] > 0 and perdus["triangle_sym_bas"] > 0
    # et ne touchent rien ailleurs
    for t, s in _series_reelles():
        c = s["c"]
        autres = lambda sig: [x for x in sig if not x[1].startswith(("ete", "triangle", "oblique", "canal"))]
        assert autres(figures(c, regles=V1)) == autres(figures(c, regles=V2)), t


# ── 5. le volume : une information, jamais un filtre ────────────────────

def test_ratio_volume_a_la_main():
    v = np.array([10.0] * 20 + [30.0, 5.0])
    assert rs.ratio_volume(v, 20) == 3.0              # 30 / médiane(10 × 20)
    assert rs.ratio_volume(v, 21) == pytest.approx(5.0 / 10.0)
    assert rs.ratio_volume(v, 19) is None             # moins de 20 séances de recul
    assert rs.ratio_volume(np.zeros(25), 22) is None  # médiane nulle
    assert rs.ratio_volume(None, 22) is None
    # la médiane, pas la moyenne : un pic isolé ne gonfle pas le dénominateur
    w = np.array([10.0] * 19 + [1000.0, 40.0])
    assert rs.ratio_volume(w, 20) == 4.0


def test_le_volume_ne_filtre_rien():
    for t, s in _series_reelles():
        sans = figures_detail(s["c"]) + lignes_detail(s["c"])
        avec = figures_detail(s["c"], v=s["v"]) + lignes_detail(s["c"], v=s["v"])
        cle = lambda f: (f["type"], f["conf"], f["statut"], f["i_fin"])
        assert [cle(f) for f in sans] == [cle(f) for f in avec], t


def test_publie_porte_les_regles_et_le_volume_en_information():
    pub = json.loads(PUBLIE.read_text(encoding="utf-8"))
    assert pub["regles"] == V2 and pub["methode"]["regles"]["date"] == V2
    assert V1 in pub["methode"]["regles"]["ancien_jeu_accessible"]
    assert pub["methode"]["artefacts"]["figures_lignes"].endswith("etape4_regles_2026-10-21.json")
    vus = 0
    for v in pub["titres"].values():
        for x in v["figures"] + v["lignes"]:
            if x["statut"] == "declenchee" and not x["type"].startswith("fibo_"):
                assert "volume_cassure_ratio" in x
                assert x["volume_cassure_ratio"] is None or x["volume_cassure_ratio"] > 0
                vus += 1
            else:
                assert "volume_cassure_ratio" not in x
    assert vus > 20
    assert "aucun filtre" in pub["methode"]["volume"].lower() or "information seule" in pub["methode"]["volume"].lower()


def test_les_frequences_publiees_viennent_de_l_artefact_du_nouveau_jeu():
    pub = json.loads(PUBLIE.read_text(encoding="utf-8"))
    art = json.loads((RACINE / fp.ARTEFACTS_ALPHA[V2]).read_text(encoding="utf-8"))
    assert art["regles"] == V2
    n = sum(art["signaux"]["ete"]["tous"][p]["h20"]["n"] for p in ("2023-10_2024-12", "2025-01_2026-10"))
    assert pub["frequences"]["ete"]["univers"]["tous"]["n"] == n
    # l'ancien artefact reste en place pour la comparaison
    assert (RACINE / fp.ARTEFACTS_ALPHA[V1]).exists()
    assert (RACINE / "datasets" / "calibrage_technique" / "comparaison_regles_2026-10-21.json").exists()
