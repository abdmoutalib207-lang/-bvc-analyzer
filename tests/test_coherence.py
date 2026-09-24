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

from coherence import ADX_SANS_TENDANCE, controler, controler_tous  # noqa: E402


def _t(**kw):
    """Un titre publié, cohérent par défaut. Chaque test ne casse qu'un point.

    ⚠️ Le socle vaut exactement 6,21 : fond 7,25×52 + nlp 5,0×28 + tech 5,2×20.
    Calculé à la main, pas par la fonction testée.
    """
    base = {
        "symbol": "ZZZ", "close": 95.05, "open": 96.2,
        "h52w": 121.45, "l52w": 89.99,
        "ma20": 97.66, "ma50": 95.71, "ma200": 99.18,
        "rsi": 41.6, "adx": 22.9, "stoch_k": 23.86, "stoch_d": 31.39,
        "score_fond": 7.25, "score_nlp": 5.0, "score_tech": 5.2,
        "poids": {"f": 52, "n": 28, "t": 20}, "v53": 6.21, "bvc": 7.08,
        "nlp": 0.0, "nlp_corpus": 0.0, "nlp_news": 0.0,
        "setup": "NEUTRE", "sig": "SURVEILLER ★",
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


def test_un_sentiment_hors_intervalle_est_vu():
    assert "hors_bornes" in _codes(_t(nlp=1.4, nlp_corpus=1.4, nlp_news=0.0))


# ── Les poids ──────────────────────────────────────────────────────────────

def test_des_poids_qui_ne_font_pas_cent_sont_une_erreur():
    a = controler(_t(poids={"f": 52, "n": 28, "t": 30}))
    assert any(x["code"] == "poids_somme" and x["gravite"] == "erreur" for x in a)


def test_un_arrondi_a_un_point_pres_est_tolere():
    """⚠️ Trois arrondis d'un calcul normalisé peuvent donner 99 ou 101.
    Sans cette tolérance, le contrôle rougirait sur des runs parfaitement
    sains — et on apprendrait à l'ignorer."""
    assert "poids_somme" not in _codes(_t(poids={"f": 52, "n": 28, "t": 21}))


# ── ⚠️ Le score doit se refaire à la main ──────────────────────────────────

def test_un_score_irreproductible_est_une_erreur():
    """LE CONTRÔLE CENTRAL. Si la note ne se retrouve pas depuis les trois
    notes et les trois poids publiés, l'un des sept chiffres est faux — et le
    lecteur qui refait le calcul le verra avant nous."""
    a = controler(_t(v53=9.4))
    assert any(x["code"] == "score_irreproductible" and x["gravite"] == "erreur"
               for x in a)


def test_l_ecart_des_bonus_documentes_ne_declenche_pas():
    """⚠️ Le cas voisin, et il est essentiel : la note v5.3 porte des bonus et
    malus par-dessus le socle — jusqu'à ±1,5 point. Les compter comme une
    incohérence ferait rougir les titres les plus commentés du terminal."""
    assert "score_irreproductible" not in _codes(_t(v53=7.3))
    assert "score_irreproductible" not in _codes(_t(v53=5.1))


def test_un_titre_sans_decomposition_n_est_pas_accuse():
    """Un titre dont les briques ne sont pas publiées ne peut pas être vérifié.
    Ne rien dire est alors la seule réponse honnête — inventer un verdict sur
    une absence serait pire que le silence."""
    t = _t()
    for k in ("score_fond", "score_nlp", "score_tech"):
        t.pop(k)
    assert "score_irreproductible" not in _codes(t)


# ── ⚠️ La conviction directionnelle sans tendance ──────────────────────────

def test_un_setup_directionnel_sous_adx_20_est_signale():
    """La faille relevée de l'extérieur : le score retient une conviction de
    direction là où son PROPRE indicateur de force dit qu'il n'y a pas de
    tendance. 18 titres sur 80 étaient dans ce cas au 24/09."""
    assert "direction_sans_tendance" in _codes(_t(adx=19, setup="CONTRARIEN"))


def test_un_setup_neutre_sous_adx_20_ne_l_est_pas():
    """Le cas voisin : un ADX bas AVEC un setup neutre, c'est la cohérence
    même. C'est ce que le terminal devrait afficher plus souvent."""
    assert "direction_sans_tendance" not in _codes(_t(adx=19, setup="NEUTRE"))


def test_un_setup_directionnel_avec_tendance_ne_l_est_pas():
    assert "direction_sans_tendance" not in _codes(
        _t(adx=ADX_SANS_TENDANCE + 5, setup="CONTRARIEN"))


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


# ── La décomposition du sentiment ──────────────────────────────────────────

def test_un_nlp_qui_ne_vaut_pas_ses_composantes_est_signale():
    assert "nlp_decompose_faux" in _codes(
        _t(nlp=0.5, nlp_corpus=0.1, nlp_news=0.1))


def test_la_somme_exacte_ne_declenche_rien():
    assert "nlp_decompose_faux" not in _codes(
        _t(nlp=0.2, nlp_corpus=0.1, nlp_news=0.1))


# ── Le signal exige de la confiance ────────────────────────────────────────

def test_un_signal_sans_confiance_est_une_erreur():
    """L'anti-pattern nommé dans le CLAUDE.md : « ne pas émettre ACHAT/ÉVITER
    si confidence ≤ 1 »."""
    t = _t(sig="ACHAT FORT ★★★")
    t["_meta"]["confidence"] = 1
    assert "signal_sans_confiance" in _codes(t)


def test_surveiller_sans_confiance_n_est_pas_accuse():
    """Le cas voisin : « SURVEILLER » n'est pas une décision, c'est une
    invitation à regarder. La règle vise ACHAT et ÉVITER."""
    t = _t(sig="SURVEILLER ★")
    t["_meta"]["confidence"] = 0
    assert "signal_sans_confiance" not in _codes(t)


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
                        _t(symbol="CCC", adx=19, setup="CONTRARIEN")])
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
