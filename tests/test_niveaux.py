#!/usr/bin/env python3
"""Un niveau sans sa méthode est une opinion déguisée en nombre.

⚠️ CE QUE CES TESTS DÉFENDENT
─────────────────────────────
Un briefing extérieur lu le 25/09/2026 écrit : « SGTM — 620 = pivot ; reprise
635-645 = pullback digéré ». Les chiffres sont peut-être justes. **Rien ne dit
d'où ils viennent**, donc personne ne peut les reproduire ni les contester.

Ce module range les niveaux en deux familles qui ne s'arbitrent pas ensemble :

  FAITS        ce que le marché a fait, ou ce que la règle interdit de
               dépasser — bornes ±10 % (R10), extrêmes atteints, moyennes
               calculées sur des clôtures réelles.
  CONVENTIONS  de l'arithmétique sur une séance — les points pivots.

Les mélanger dans une même liste, c'est les confondre tout court. Un test
l'empêche.

⚠️ LA BORNE RÉGLEMENTAIRE EST LE NIVEAU LE PLUS SÛR, et personne ne le publie
comme tel : le cours de demain est borné PAR LA LOI, pas par une opinion.
Minière Touissit a touché ce plafond cinq séances d'affilée — c'est le seul
niveau qui ait décrit la réalité sur ce titre.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import niveaux as nv  # noqa: E402


# ── ⚠️ Le fait et la convention ne se mélangent pas ────────────────────────

def test_les_deux_familles_sont_separees_dans_la_sortie():
    """⚠️ LE TEST CENTRAL. Un lecteur doit voir d'un coup d'œil ce qui est
    établi et ce qui est conventionnel."""
    r = nv.composer({"price": 620.0, "ma20": 636.38, "h52w": 989.0,
                     "_meta": {"n_candles": 165}},
                    {"d": "2026-09-24", "o": 640.0, "h": 645.0, "l": 616.0,
                     "c": 620.0})
    assert "bornes_seance" in r["faits"]
    assert "pivots" in r["conventions"]
    assert "pivots" not in r["faits"], (
        "un pivot rangé parmi les faits se lirait comme une mesure")


def test_chaque_famille_porte_sa_methode():
    """Un niveau publié sans sa méthode n'est pas vérifiable."""
    r = nv.composer({"price": 620.0, "ma20": 636.38, "h52w": 989.0,
                     "_meta": {"n_candles": 165}},
                    {"d": "2026-09-24", "o": 640.0, "h": 645.0, "l": 616.0,
                     "c": 620.0})
    assert "_methode" in r["faits"]["bornes_seance"]
    assert "_methode" in r["conventions"]["pivots"]
    assert "CONVENTION" in r["conventions"]["pivots"]["_methode"], (
        "la nature conventionnelle des pivots doit être écrite dans la sortie, "
        "pas seulement dans le code")


# ── ⚠️ Les bornes réglementaires : un fait, pas un avis ────────────────────

def test_les_bornes_valent_dix_pour_cent_de_la_cloture():
    """Attendu calculé à la main : 620 × 0,90 = 558 ; 620 × 1,10 = 682."""
    b = nv.bornes_reglementaires(620.0)
    assert b["plancher"] == 558.0
    assert b["plafond"] == 682.0


def test_les_bornes_existent_meme_sans_historique():
    """⚠️ C'est ce qui les rend précieuses : un titre fraîchement introduit,
    sans moyenne ni extrême annuel, a quand même une borne. Elle ne dépend
    d'aucune série."""
    r = nv.composer({"price": 100.0, "_meta": {"n_candles": 3}}, None)
    assert r["faits"]["bornes_seance"]["plafond"] == 110.0
    assert "moyennes" not in r["faits"]
    assert "conventions" not in r


def test_un_cours_absent_ne_produit_pas_de_borne():
    assert nv.bornes_reglementaires(None) is None
    assert nv.bornes_reglementaires(0) is None


# ── ⚠️ Les pivots, et les cas où ils ne veulent rien dire ──────────────────

def test_les_pivots_suivent_la_formule_classique():
    """Attendu à la main sur H=645, B=616, C=620 :
        P  = (645 + 616 + 620) / 3 = 627,00
        R1 = 2×627 − 616 = 638,00      S1 = 2×627 − 645 = 609,00
        R2 = 627 + 29    = 656,00      S2 = 627 − 29    = 598,00
    """
    p = nv.pivots({"d": "2026-09-24", "h": 645.0, "l": 616.0, "c": 620.0})
    assert p["pivot"] == 627.0
    assert p["r1"] == 638.0 and p["s1"] == 609.0
    assert p["r2"] == 656.0 and p["s2"] == 598.0


def test_une_seance_d_amplitude_nulle_ne_produit_pas_de_pivots():
    """⚠️ LE CAS RÉEL, et il concerne 20 titres sur 80 au 25/09.

    Minière Touissit a clôturé au plafond : `o = h = l = c = 3923`, 51 titres
    échangés. Les pivots s'y réduisent tous à la clôture et n'apprennent rien.
    Une séance RÉPARÉE porte la même signature (`o = h = l = c`, `v = 0`).

    Publier P = R1 = S1 = 3923 donnerait cinq « niveaux » qui sont un seul
    chiffre recopié.
    """
    assert nv.pivots({"d": "2026-09-24", "o": 3923.0, "h": 3923.0,
                      "l": 3923.0, "c": 3923.0, "v": 51}) is None


def test_un_ohlc_incoherent_est_refuse():
    """Un plus-haut sous le plus-bas est une donnée fausse, pas un niveau."""
    assert nv.pivots({"h": 100.0, "l": 200.0, "c": 150.0}) is None
    assert nv.pivots({"h": 100.0, "c": 150.0}) is None
    assert nv.pivots("pas un dictionnaire") is None


# ── ⚠️ Les moyennes ne se publient pas sans leur fenêtre ───────────────────

def test_une_moyenne_est_tue_si_la_fenetre_manque():
    """⚠️ SGTM porte 165 chandelles : sa MA200 ne repose sur rien. Le champ
    peut exister dans le flux — le publier comme niveau serait affirmer une
    moyenne qu'on n'a pas les moyens de calculer."""
    r = nv.moyennes({"price": 620.0, "ma20": 636.0, "ma50": 672.0,
                     "ma200": 700.0, "_meta": {"n_candles": 165}})
    assert "ma20" in r and "ma50" in r
    assert "ma200" not in r, "une MA200 publiée sur 165 séances est une fiction"


def test_la_position_du_cours_est_explicite():
    """« 701 » ne dit pas si le titre est au-dessus ou en dessous."""
    r = nv.moyennes({"price": 680.5, "ma20": 701.21,
                     "_meta": {"n_candles": 810}})
    assert r["ma20"]["position"] == "en dessous"
    # attendu à la main : 701,21 / 680,5 − 1 = +3,04 %
    assert r["ma20"]["distance_pct"] == 3.04


def test_les_extremes_portent_leur_distance_au_cours():
    """⚠️ « 804 » ne dit rien seul quand le titre vaut 680. C'est « 18 %
    au-dessus » qui informe."""
    r = nv.extremes({"price": 680.5, "h52w": 804.0, "l52w": 663.1})
    assert r["plus_haut_52s"]["distance_pct"] == 18.15
    assert r["plus_bas_52s"]["distance_pct"] == -2.56


# ── ⚠️ Ce que ces niveaux ne font pas ──────────────────────────────────────

def test_les_niveaux_n_entrent_dans_aucun_score():
    """⚠️ R8. Les y faire entrer déplacerait la note de tous les titres.
    Lu par l'AST : le module ne doit manipuler aucun champ de score."""
    import ast
    arbre = ast.parse((RACINE / "pipeline" / "niveaux.py").read_text(encoding="utf-8"))
    for n in ast.walk(arbre):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            assert n.value not in {"v53", "bvc", "score_tech", "score_fond",
                                   "score_nlp", "poids", "sig"}, (
                f"le module des niveaux manipule « {n.value} »")


def test_la_sortie_ne_donne_aucun_conseil_de_position():
    """⚠️ « Zone de défense », « aucun renforcement », « ne pas poursuivre à
    l'ouverture » sont des conseils. Ce module publie des nombres et leur
    méthode ; ce que le lecteur en fait lui appartient."""
    r = nv.composer({"price": 620.0, "h52w": 989.0, "_meta": {"n_candles": 165}},
                    {"d": "2026-09-24", "h": 645.0, "l": 616.0, "c": 620.0})
    texte = json.dumps(r, ensure_ascii=False).lower()
    for mot in ("acheter", "vendre", "renforcer", "alléger", "ne pas ",
                "prioriser", "conseill"):
        assert mot not in texte, f"la sortie contient un conseil : « {mot} »"


# ── Le flux publié et l'écran ──────────────────────────────────────────────

def test_tout_titre_publie_porte_au_moins_ses_bornes():
    """⚠️ Les bornes ne dépendent d'aucune série : un titre qui n'en a pas
    n'est pas une excuse."""
    f = RACINE / "data.json"
    if not f.exists():
        pytest.skip("data.json absent de ce clone")
    t = json.loads(f.read_text(encoding="utf-8")).get("tickers") or []
    sans = [x.get("symbol") for x in t
            if x.get("price") and not ((x.get("niveaux") or {})
                                       .get("faits", {}).get("bornes_seance"))]
    assert not sans, f"titres sans bornes réglementaires : {sans[:6]}"


def test_l_ecran_distingue_visuellement_les_deux_familles():
    """⚠️ La séparation dans les données ne sert à rien si l'écran les
    aligne dans la même liste."""
    ecran = (RACINE / "index.html").read_text(encoding="utf-8")
    assert "r.niveaux" in ecran, "les niveaux sont calculés mais invisibles"
    i = ecran.find("r.niveaux")
    bloc = ecran[i:i + 3000]
    assert "Établis" in bloc and "Conventionnels" in bloc, (
        "les deux familles ne sont pas distinguées à l'écran")
    assert "règle BVC" in bloc, (
        "la borne réglementaire s'affiche sans dire qu'elle vient de la règle")


# ── ⚠️ Deux bornes coexistent, et elles ne disent pas la même chose ────────

def test_la_borne_publiee_est_le_plafond_journalier_pas_la_reservation():
    """⚠️ LA CONFUSION QUE CE TEST EMPÊCHE — elle a failli être commise.

    Le fournisseur sert `SeuilBas`/`SeuilHaut`, qu'on pourrait prendre pour
    la borne réglementaire. Relevé sur 81 instruments le 25/09/2026 :

        33 affichent exactement ±3,00 %
         1 affiche ±10 %
        47 sont ASYMÉTRIQUES

    Ce sont les bornes de RÉSERVATION intraday, qui glissent avec le cours.
    Les publier comme borne du jour donnerait une fourchette trois fois trop
    étroite présentée comme la règle.

        réservation ±3 %   borne un ÉCHANGE ; la franchir suspend la cotation
        plafond ±10 %      borne la VARIATION de la séance entière (R10)

    Attendu à la main : 100 × 1,10 = 110, et non 103.
    """
    b = nv.bornes_reglementaires(100.0)
    assert b["plafond"] == 110.0, "la borne publiée n'est pas le plafond du jour"
    assert b["plancher"] == 90.0


def test_la_methode_distingue_les_deux_mecanismes():
    """⚠️ La distinction doit être lisible dans la SORTIE, pas seulement dans
    le code : c'est le lecteur qui doit pouvoir la faire."""
    assert "réservation" in nv.bornes_reglementaires.__doc__.lower()
    assert "R10" in nv.bornes_reglementaires(100.0)["_methode"]


def test_le_moteur_collecte_le_montant_reellement_echange():
    """⚠️ Le fournisseur sert `Volumes` — le montant réel — et le projet ne
    lisait que la QUANTITÉ, approchant partout par `volume × clôture`.

    Écart mesuré contre deux briefings extérieurs sur la séance du 24/09 :
    TGCC 26,15 M DH réels contre 25,96 approchés ; MSA 16,86 contre 16,77.
    """
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert '"echange_dh": _f(d.get("Volumes"))' in src, (
        "le montant réellement échangé n'est pas collecté")
    assert '"seuil_bas":  _f(d.get("SeuilBas"))' in src, (
        "les bornes de réservation ne sont pas collectées")
