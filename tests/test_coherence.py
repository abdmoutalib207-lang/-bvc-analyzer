#!/usr/bin/env python3
"""Ce que le contrôle de cohérence doit voir, et ce qu'il ne doit pas inventer.

⚠️ SES DEUX FAUTES POSSIBLES SONT OPPOSÉES
──────────────────────────────────────────
  taire une incohérence   → le terminal publie deux chiffres qui ne peuvent
                            pas être vrais ensemble, et personne ne le sait ;
  en inventer une         → le relevé se remplit de bruit, on apprend à ne plus
                            le lire, et il ne protège plus rien.

La seconde est la plus insidieuse : un contrôle qu'on ignore coûte le prix d'un
contrôle et rend le service de zéro. C'est ce qui est arrivé au « réveil des
robots », qui annonçait le succès de sa propre inaction pendant quatre
semaines.

D'où une règle pour chaque test ci-dessous : il y a toujours le cas qui DOIT
rougir, et le cas voisin qui ne doit PAS.

⚠️ CE MODULE NE DIT PAS SI UN CHIFFRE EST VRAI
Une série peut être entièrement fausse et parfaitement cohérente. L'inverse,
non : une incohérence prouve qu'au moins un chiffre est faux — sans dire
lequel, et c'est pourquoi le module signale au lieu de corriger.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import pytest  # noqa: E402

from coherence import controler, controler_tous  # noqa: E402


def _t(**kw):
    """Un titre publié, cohérent par défaut. Chaque test ne casse qu'un point.

    ⚠️ 06/11/2026 : plus de `score_fond`, `score_tech`, `poids`, `v53`,
    `setup` ni `sig` — le producteur de la note v5.3 est retiré (lot 2).
    """
    base = {
        "symbol": "ZZZ", "close": 95.05, "open": 96.2,
        "h52w": 121.45, "l52w": 89.99,
        "ma20": 97.66, "ma50": 95.71, "ma200": 99.18,
        "rsi": 41.6, "adx": 22.9, "stoch_k": 23.86, "stoch_d": 31.39,
        "bvc": 7.08,
        "_meta": {"confidence": 5, "fond_asof": "2026-06-18",
                  "fond_age_jours": 98, "source_fond": "bpa_calcule"},
    }
    base.update(kw)
    return base


def _codes(t):
    return {a["code"] for a in controler(t)}


def test_un_titre_sain_ne_declenche_rien():
    """⚠️ LE TEST QUI PROTÈGE DU BRUIT. S'il rougit, tous les autres perdent
    leur sens : un contrôle qui accuse le cas normal n'accuse rien."""
    assert controler(_t()) == []


# ── Les bornes mathématiques ───────────────────────────────────────────────

def test_un_rsi_hors_bornes_est_une_erreur():
    """Un RSI à 140 n'est pas un RSI extrême, c'est un calcul faux."""
    a = controler(_t(rsi=140))
    assert any(x["code"] == "hors_bornes" and x["gravite"] == "erreur" for x in a)


def test_un_rsi_extreme_mais_valide_ne_declenche_rien():
    """Le cas voisin : 0 et 100 sont atteignables, et ne prouvent rien."""
    assert "hors_bornes" not in _codes(_t(rsi=0))
    assert "hors_bornes" not in _codes(_t(rsi=100))


def test_les_bornes_du_pilier_nlp_sont_retirees():
    """⚠️ RETOURNÉ LE 29/10/2026. Ce test exigeait qu'un sentiment hors
    [-1, 1] soit vu ; le pilier NLP est retiré du moteur et ses champs ne
    sont plus publiés. Leurs bornes ne doivent pas revenir."""
    from coherence import BORNES
    assert not {"nlp", "nlp_corpus", "nlp_news", "score_nlp"} & set(BORNES)


# ── ⚠️ 06/11/2026 : les contrôles de la note v5.3 sont retirés ────────────
# Retrait du producteur (lot 2, décision d'Abd Moutalib : « l'ancien scoring
# doit disparaître »). « poids_somme », « score_irreproductible »,
# « direction_sans_tendance » (setup) et « signal_sans_confiance » vérifiaient
# des champs que le moteur ne publie plus ; les bornes `v53`, `score_fond`,
# `score_tech` partent avec eux. Le Score BVC se refait à la main au
# contrôle 10 (tests/test_score_bvc.py). Les anciens cas sont retournés : un
# data.json écrit AVANT la fusion porte encore ces champs, et même faux ils ne
# doivent plus rien déclencher — l'outil ne juge que ce qui est publié.

CODES_V53 = {"poids_somme", "score_irreproductible", "direction_sans_tendance",
             "signal_sans_confiance"}


def test_les_bornes_de_la_note_v53_sont_retirees():
    from coherence import BORNES
    assert not {"v53", "score_fond", "score_tech"} & set(BORNES)


@pytest.mark.parametrize("champs", [
    {"poids": {"f": 65, "t": 45}},
    {"poids": {"f": 52, "n": 28, "t": 20}},
    {"score_fond": 7.25, "score_tech": 5.2, "poids": {"f": 65, "t": 35}, "v53": 9.4},
    {"v53": 14.0, "score_fond": -3, "score_tech": 11},
    {"adx": 19, "setup": "CONTRARIEN"},
    {"sig": "ACHAT FORT ★★★", "_meta": {"confidence": 1}},
])
def test_les_champs_v53_d_un_ancien_fichier_ne_declenchent_plus_rien(champs):
    assert controler(_t(**champs)) == []


# ── L'identité et les extrêmes ─────────────────────────────────────────────

def test_une_moyenne_hors_echelle_est_une_erreur():
    """Un facteur 3 entre le cours et sa moyenne signale un ISIN croisé — le
    cours d'une société mariée à l'historique d'une autre. C'est ainsi que
    Sonasid a porté les cotations de Stokvis."""
    a = controler(_t(ma50=400.0))
    assert any(x["code"] == "ma_hors_echelle" and x["gravite"] == "erreur"
               for x in a)


def test_des_extremes_inverses_sont_une_erreur():
    a = controler(_t(h52w=80, l52w=120))
    assert any(x["code"] == "extremes_inverses" for x in a)


def test_un_cours_au_dessus_du_plus_haut_est_signale():
    assert "cours_hors_extremes" in _codes(_t(close=200))


def test_un_cours_egal_au_plus_haut_ne_l_est_pas():
    """Le jour où un titre fait son plus haut, le cours VAUT le plus haut.
    Accuser ce cas rougirait à chaque record."""
    assert "cours_hors_extremes" not in _codes(_t(close=121.45))


# ── La décomposition du sentiment (contrôle n°7, retiré le 29/10/2026) ───

def test_le_controle_de_decomposition_du_sentiment_est_retire():
    """⚠️ RETOURNÉ. « nlp_decompose_faux » vérifiait nlp = corpus + news ; les
    trois champs ne sont plus publiés et le pilier est retiré du moteur. Même
    une décomposition fausse ne doit plus produire ce code."""
    assert "nlp_decompose_faux" not in _codes(
        _t(nlp=0.5, nlp_corpus=0.1, nlp_news=0.1))


# ── La fraîcheur ───────────────────────────────────────────────────────────

def test_des_fondamentaux_de_plus_de_six_mois_sont_signales():
    t = _t()
    t["_meta"]["fond_age_jours"] = 200
    assert "fondamentaux_perimes" in _codes(t)


def test_des_fondamentaux_sans_date_sont_signales():
    t = _t()
    t["_meta"].pop("fond_age_jours")
    t["_meta"].pop("fond_asof")
    assert "fondamentaux_sans_date" in _codes(t)


def test_quatre_vingt_dix_huit_jours_ne_declenchent_pas():
    """⚠️ L'âge réel au 24/09. Le signaler comme périmé ferait rougir les 77
    sociétés d'un coup, et le relevé deviendrait illisible. Le seuil dit
    « anormal », pas « vieux » — la vieillesse, elle, s'affiche sur la fiche."""
    assert "fondamentaux_perimes" not in _codes(_t())


# ── Le relevé d'ensemble ───────────────────────────────────────────────────

def test_le_releve_compte_par_code_et_par_titre():
    r = controler_tous([_t(symbol="AAA"),
                        _t(symbol="BBB", rsi=140),
                        _t(symbol="CCC", close=200)])
    assert r["titres_controles"] == 3
    assert r["titres_avec_anomalie"] == 2
    assert r["erreurs"] == 1
    assert r["par_code"]["hors_bornes"] == 1
    assert "AAA" not in r["detail"]


def test_une_ligne_malformee_ne_fait_pas_tomber_le_releve():
    """⚠️ Un contrôle qui s'effondre sur une ligne abîmée laisse passer tout le
    reste du flux — il faut qu'il survive à ce qu'il est censé attraper."""
    r = controler_tous([None, "pas un dict", {}, _t(symbol="AAA")])
    assert r["titres_controles"] == 4


def test_le_controle_ne_modifie_pas_le_titre():
    """Il RELÈVE, il ne corrige pas. Devant « RSI 29 ici et 41 là », rien ne
    permet de choisir, et choisir au hasard effacerait le symptôme en gardant
    la maladie."""
    import copy
    t = _t(rsi=140)
    avant = copy.deepcopy(t)
    controler(t)
    assert t == avant


# ── Le flux publié ─────────────────────────────────────────────────────────

def test_le_flux_publie_ne_porte_aucune_erreur_de_coherence():
    """⚠️ Le contrôle sur la LIVRAISON. Les avertissements sont tolérés — ils
    décrivent des chantiers ouverts — mais une ERREUR signifie que deux
    chiffres publiés ne peuvent pas être vrais ensemble."""
    import json
    import pytest
    chemin = RACINE / "data.json"
    if not chemin.exists():
        pytest.skip("data.json absent de ce clone")
    flux = json.loads(chemin.read_text(encoding="utf-8"))
    r = controler_tous(flux.get("tickers") or [])
    graves = {s: [x for x in a if x["gravite"] == "erreur"]
              for s, a in r["detail"].items()}
    graves = {s: a for s, a in graves.items() if a}
    assert not graves, (
        f"{r['erreurs']} incohérence(s) dans le flux publié : "
        + "; ".join(f"{s} — {a[0]['quoi']}" for s, a in list(graves.items())[:5]))


# ── ⚠️ Le Score BVC se refait à la main — 06/11/2026 (lot 1) ───────────────

def _bvc():
    """Un bloc conforme, calculé à la main : 15 + 15 + 10 + 2 + 7,5 + 0 = 49,5
    points sur une couverture de 100 → 49,5."""
    return {"valeur": 49.5, "etat": "CALCULABLE", "couverture_pct": 100, "version": "bvc-score-v1",
            "motif": None, "facteurs": {
                "moyennes_mobiles": {"poids": 35, "points": 15.0},
                "momentum": {"poids": 15, "points": 15.0},
                "macd": {"poids": 10, "points": 10.0},
                "activité": {"poids": 10, "points": 2.0},
                "liquidité": {"poids": 15, "points": 7.5},
                "rentabilité": {"poids": 15, "points": 0.0}}}


def test_un_score_bvc_sain_ne_declenche_rien():
    assert controler(_t(score_bvc=_bvc())) == []


def test_un_score_bvc_qui_ne_se_recompose_pas_est_une_erreur():
    b = _bvc()
    b["valeur"] = 55.0
    assert "score_bvc_irreproductible" in _codes(_t(score_bvc=b))
    b = _bvc()
    b["couverture_pct"] = 85          # ≠ 100, somme des poids disponibles
    assert "score_bvc_irreproductible" in _codes(_t(score_bvc=b))


def test_un_facteur_indisponible_sort_de_la_couverture():
    """Rentabilité sans ROE publié : points None, la couverture tombe à 85 et
    la valeur se rapporte à 85 — 49,5 / 85 × 100 = 58,24."""
    b = _bvc()
    b["facteurs"]["rentabilité"]["points"] = None
    b["couverture_pct"], b["valeur"] = 85, 58.24
    assert controler(_t(score_bvc=b)) == []
    # MM200 indisponible (moins de 200 séances, cas de ZLD au 05/11) : le poids
    # COUVERT des moyennes mobiles tombe à 25, la couverture à 90.
    b = _bvc()
    b["facteurs"]["moyennes_mobiles"]["poids"] = 25
    b["couverture_pct"], b["valeur"] = 90, 55.0
    assert controler(_t(score_bvc=b)) == []


def test_l_etat_et_la_valeur_vont_ensemble():
    b = _bvc()
    b["etat"] = "PARTIEL"
    assert "score_bvc_etat" in _codes(_t(score_bvc=b))
    b = _bvc()
    b["valeur"] = None
    assert "score_bvc_etat" in _codes(_t(score_bvc=b))
    b = _bvc()
    b["etat"] = "PEUT-ÊTRE"
    assert "score_bvc_etat" in _codes(_t(score_bvc=b))


def test_un_score_bvc_hors_bornes_ou_sous_le_seuil_est_une_erreur():
    b = _bvc()
    b["valeur"] = 140
    assert "hors_bornes" in _codes(_t(score_bvc=b))
    b = _bvc()
    for f in ("macd", "activité", "liquidité", "rentabilité"):
        b["facteurs"][f]["points"] = None
    b["couverture_pct"], b["valeur"] = 50, 60.0
    assert "score_bvc_couverture" in _codes(_t(score_bvc=b))


def test_un_score_bvc_sur_un_cours_perime_ou_suspendu_est_une_erreur():
    meta = dict(_t()["_meta"], stale=True)
    assert "score_bvc_sur_cours_perime" in _codes(_t(score_bvc=_bvc(), _meta=meta))
    nc = {"valeur": None, "etat": "NON_CALCULABLE", "couverture_pct": 0, "facteurs": {},
          "version": "bvc-score-v1", "motif": "cotation suspendue"}
    assert controler(_t(score_bvc=nc, _meta=dict(_t()["_meta"], suspendu=True))) == []


def test_les_fondamentaux_perimes_ne_citent_plus_le_poids_de_la_note_v53():
    t = _t()
    t["_meta"]["fond_age_jours"] = 200
    quoi = [a["quoi"] for a in controler(t) if a["code"] == "fondamentaux_perimes"][0]
    assert "poids" not in quoi and "note fondamentale" in quoi
