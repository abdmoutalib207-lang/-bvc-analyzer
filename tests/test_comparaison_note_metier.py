"""Le livrable de comparaison note actuelle / note par métier (11/10/2026).

Contrôles de STRUCTURE et d'invariants (pas de valeurs figées : les données
bougent chaque jour) : 80 titres, chaque critère porte état, valeur, source,
période, base, poids nominal et effectif, référence ; les poids effectifs d'un
titre noté somment à 100 ; les états sont les cinq prévus ; la synthèse
recompte ce que le détail contient ; le calcul est déterministe.
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import pytest  # noqa: E402

import comparaison_note_metier as cm  # noqa: E402
from pipeline.smart_money import fond_score_sectoriel as fs  # noqa: E402


@pytest.fixture(scope="module")
def comparaison():
    return cm.construire()


def test_quatre_vingts_titres_chacun_avec_ses_criteres(comparaison):
    t = comparaison["titres"]
    assert len(t) == 80
    for s, x in t.items():
        assert {"famille", "note_actuelle", "note_metier", "criteres", "dependance_cote"} <= set(x), s
        assert set(x["criteres"]) == set(fs.POIDS), s
        for nom, c in x["criteres"].items():
            assert {"etat", "valeur", "source", "periode", "base", "poids_nominal", "poids_effectif",
                    "reference", "note", "motif"} <= set(c), (s, nom)
            assert c["etat"] in ("present", "absent", "zero_confirme", "remplacement", "suspendu"), (s, nom)
            if c["etat"] in ("absent", "suspendu"):
                assert c["note"] is None and c["poids_effectif"] == 0 and c["motif"], (s, nom, "doit dire pourquoi")


def test_les_poids_effectifs_d_un_titre_note_somment_a_cent(comparaison):
    for s, x in comparaison["titres"].items():
        if x["note_metier"] is None:
            assert all(c["poids_effectif"] == 0 for c in x["criteres"].values()) or x["poids_disponible"] < 50, s
        else:
            assert round(sum(c["poids_effectif"] for c in x["criteres"].values())) == 100, s
            assert x["poids_disponible"] >= fs.SEUIL_POIDS


def test_la_synthese_recompte_le_detail(comparaison):
    sy, t = comparaison["synthese"], comparaison["titres"]
    assert sy["notes_metier"] + sy["sans_note_metier"] == sy["titres"] == 80
    assert sy["notes_metier"] == sum(1 for x in t.values() if x["note_metier"] is not None)
    for k in fs.POIDS:
        assert sum(sy["etats_par_critere"][k].values()) == 80
    assert sum(sy["base_du_roe"].values()) == 80
    assert sum(v["n"] for v in sy["par_famille"].values()) == 80
    dep = sy["dependance_a_la_cote_entiere"]
    assert dep["titres_concernes"] == len(dep["liste"])


def test_les_foncieres_n_ont_pas_de_note_et_la_cote_entiere_est_etiquetee(comparaison):
    t = comparaison["titres"]
    for s in ("ARD", "IMI", "BAL"):
        assert t[s]["note_metier"] is None, "limite annoncée : ROE et bilan suspendus, P/B inutilisable"
    for s, x in t.items():
        ref = x["criteres"]["valorisation"]["reference"]
        if ref and ref["type"] == "cote_entiere":
            assert "NON sectorielle" in ref["libelle"] and "NON sectorielle" in x["criteres"]["valorisation"]["mesure"]


def test_la_comparaison_ne_change_aucun_signal_publie(comparaison):
    # Les champs « actuels » sont recopiés de data.json, jamais recalculés.
    data = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    for t in data["tickers"]:
        x = comparaison["titres"][t["symbol"]]
        assert x["note_actuelle"] == t.get("score_fond") and x["v53_actuelle"] == t.get("v53")
        assert x["signal_actuel"] == t.get("sig")


def test_deterministe():
    a = json.dumps(cm.construire(), ensure_ascii=False, sort_keys=True)
    b = json.dumps(cm.construire(), ensure_ascii=False, sort_keys=True)
    assert a == b


def test_une_note_partielle_n_ameliore_jamais_le_palier_simule(comparaison):
    rang = ("ÉVITER FORT", "ÉVITER", "ATTENDRE", "SURVEILLER", "ACHETER")
    for s, x in comparaison["titres"].items():
        if not x["partielle"]:
            assert x["signal_limite_par_note_partielle"] is False, s
            continue
        assert x["criteres_essentiels_manquants"], s
        a, b = x["palier_actuel"], x["palier_simule"]
        if a in rang and b in rang:
            assert rang.index(b) <= rang.index(a), f"{s} : note partielle, palier {a} → {b}"


def test_la_synthese_compte_les_notes_partielles_et_les_suspensions_par_motif(comparaison):
    sy, t = comparaison["synthese"], comparaison["titres"]
    assert sy["notes_partielles"]["nombre"] == sum(1 for x in t.values() if x["partielle"])
    n_susp = sum(1 for x in t.values() for c in x["criteres"].values() if c["etat"] == "suspendu")
    assert sum(sy["suspensions_par_motif"].values()) == n_susp
    n_abs = sum(1 for x in t.values() for c in x["criteres"].values() if c["etat"] == "absent")
    assert sum(sy["absences_par_motif"].values()) == n_abs


def test_l_effet_de_la_convention_des_fonds_propres_moyens_est_mesure(comparaison):
    e = comparaison["synthese"]["effet_convention_fonds_propres_moyens"]
    t = comparaison["titres"]
    assert (e["titres_sur_moyenne"] + e["titres_sur_cloture_moyenne_ecartee"]
            + e["titres_sur_cloture_moyenne_indisponible"] + e["titres_en_remplacement_12_mois"]
            + e["titres_sans_roe_d_exercice"]) == 80
    assert e["titres_avec_roe_d_exercice"] == (e["titres_sur_moyenne"] + e["titres_sur_cloture_moyenne_ecartee"]
                                                + e["titres_sur_cloture_moyenne_indisponible"])
    assert "NON arrondi" in e["ecart_roe_moyen_moins_cloture_non_arrondie"]["reference"]


def test_les_motifs_d_ecartement_sont_comptes_par_code_et_exactement():
    # Bogue du 14/10 : la recherche de texte « opération sur le capital » attrapait aussi le
    # motif du seuil de variation. Le compte se fait par CODE ; ce test asserte le compte EXACT.
    roes = {
        "A": {"convention": "cloture_moyenne_ecartee", "moyenne_code": "registre_operation_capital"},
        "B": {"convention": "cloture_moyenne_ecartee", "moyenne_code": "registre_operation_capital"},
        "C": {"convention": "cloture_moyenne_ecartee", "moyenne_code": "residu_non_explique"},
        "D": {"convention": "cloture_moyenne_ecartee", "moyenne_code": "base_non_confirmee"},
        "E": {"convention": "moyenne", "moyenne_code": None},
        "F": {"convention": "cloture_moyenne_indisponible", "moyenne_code": None},
    }
    assert cm.compter_motifs(roes) == {
        "opération sur le capital (registre OPERATIONS_SUR_CAPITAL)": 2,
        cm._LIBELLE_CODE["residu_non_explique"]: 1,
        "base 2024 non confirmée identique": 1}
    # Et un motif texte « opération sur le capital » côté résidu ne fausse plus rien :
    roes["C"]["moyenne_ecartee"] = "… (opération sur le capital, distribution ou résultat)"
    assert cm.compter_motifs(roes)["opération sur le capital (registre OPERATIONS_SUR_CAPITAL)"] == 2


def test_les_comptes_reels_par_motif_sont_exacts(comparaison):
    e = comparaison["synthese"]["effet_convention_fonds_propres_moyens"]
    ex = comparaison["synthese"]["roe_d_exercice_par_titre"]
    reel = {}
    for x in ex.values():
        if x["convention"] == "cloture_moyenne_ecartee":
            reel[x["code_motif"]] = reel.get(x["code_motif"], 0) + 1
    assert sum(e["moyenne_ecartee_par_motif"].values()) == e["titres_sur_cloture_moyenne_ecartee"] == sum(reel.values())
    assert e["moyenne_ecartee_par_motif"].get("opération sur le capital (registre OPERATIONS_SUR_CAPITAL)", 0) == \
        reel.get("registre_operation_capital", 0)
    for code in ("residu_non_explique", "residu_cause_sur_piece"):
        assert e["moyenne_ecartee_par_motif"].get(cm._LIBELLE_CODE[code], 0) == reel.get(code, 0), code


def test_chaque_titre_avec_roe_d_exercice_porte_sa_tracabilite(comparaison):
    ex = comparaison["synthese"]["roe_d_exercice_par_titre"]
    assert len(ex) == comparaison["synthese"]["effet_convention_fonds_propres_moyens"]["titres_avec_roe_d_exercice"]
    for s, x in ex.items():
        assert {"convention", "motif", "roe_cloture_publie", "roe_cloture_non_arrondi", "roe_moyen",
                "ecart_moyen_moins_cloture_non_arrondie", "residu_mmad", "residu_pct_fonds_propres_2024",
                "page_2025", "page_2024"} <= set(x), s
        assert x["convention"] in ("moyenne", "cloture_moyenne_ecartee", "cloture_moyenne_indisponible"), s
        if x["convention"] == "cloture_moyenne_indisponible":
            assert x["roe_moyen"] is None and x["motif"], s
        if x["roe_moyen"] is not None and x["roe_cloture_non_arrondi"] is not None:
            assert x["ecart_moyen_moins_cloture_non_arrondie"] == round(x["roe_moyen"] - x["roe_cloture_non_arrondi"], 3), s
    assert ex["SGTM"]["convention"] == "moyenne" and ex["TGCC"]["code_motif"] == "registre_operation_capital"


def test_assurances_roe_hors_gains_latents(comparaison):
    # Décision d'Abd (14/10) : ROE des assurances HORS OCI. WAF : 6,86 / 7,45 avec, 10,05 / 10,35 sans (p.16).
    oci = comparaison["synthese"]["assurances_roe_hors_gains_latents_oci"]
    assert set(oci) == {"ATL", "WAF", "SAF"}                     # toute la famille « assurance » de FAMILLES_NOTE
    w = oci["WAF"]
    assert w["oci"] == "hors OCI" and w["etat_reserve"] == "releve"
    assert w["roe_avec_oci"] == {"cloture": 6.86, "moyenne": 7.45}
    assert w["roe_hors_oci"] == {"cloture": 10.05, "moyenne": 10.35}
    assert w["convention"] == "moyenne" and w["roe_retenu"] == 10.35
    assert w["residu_hors_oci_mmad"] == -429.451 and w["residu_hors_oci_pct"] == -4.47
    assert w["residu_avec_oci_pct"] > 5, "avec OCI, le résidu aurait écarté la moyenne"
    assert w["moyenne_ecartee"] is None
    a = oci["ATL"]
    assert a["etat_reserve"] == "releve" and a["reserve_oci_2025"] == 0.0 and a["reserve_oci_2024"] == 0.0
    assert a["roe_avec_oci"] == a["roe_hors_oci"] == {"cloture": 18.84, "moyenne": 19.29}
    assert "p.140" in a["pieces"]["2025"] and "p.16" in w["pieces"]["2025"]
    s = oci["SAF"]
    assert s["oci"] == "pas de ROE d'exercice" and s["roe_retenu"] is None, "SAF : aucun ROE, rien d'estimé"


# ── seconde contre-vérification du 14/10/2026 : résidu après dividende, TMA, WAF, ATL ──

def test_le_livrable_liste_les_titres_qui_changent_de_convention(comparaison):
    ch = comparaison["synthese"]["changements_de_convention_du_residu_apres_dividende"]
    assert ch["nombre"] == len(ch["detail"])
    for s, x in ch["detail"].items():
        assert x["avant"] != x["apres"] and x["roe_avant"] is not None and x["roe_apres"] is not None, s
        assert x["residu_apres_dividende_pct"] is not None and x["motif"], s
    # CTM et BCP passent de la moyenne à la clôture : leur résidu après dividende dépasse 5 %.
    for s in ("CTM", "BCP"):
        assert ch["detail"][s]["avant"] == "moyenne" and ch["detail"][s]["apres"] == "cloture_moyenne_ecartee", s
        assert abs(ch["detail"][s]["residu_apres_dividende_pct"]) > 5
    assert ch["detail"]["CTM"]["residu_apres_dividende_pct"] == pytest.approx(-39.86, abs=0.01)
    assert ch["detail"]["BCP"]["residu_apres_dividende_pct"] == pytest.approx(-6.58, abs=0.01)
    # TMA ne change pas : son résidu après dividende est nul.
    assert "TMA" not in ch["detail"]


def test_le_rejeu_de_l_ancien_test_est_fidele():
    # Résidu avant dividende > +5 % : écartée ; négatif ou faible : moyenne ; autres codes inchangés.
    base = {"convention": "moyenne", "valeur": 20.0, "valeur_moyenne": 20.0, "valeur_cloture_publiee": 18.0,
            "moyenne_code": None, "residu_pct": -50.0}
    assert cm._roe_selon_ancien_test(base) == ("moyenne", 20.0)
    assert cm._roe_selon_ancien_test(base | {"residu_pct": 5.1}) == ("cloture_moyenne_ecartee", 18.0)
    assert cm._roe_selon_ancien_test(base | {"residu_pct": 5.0}) == ("moyenne", 20.0)
    reg = base | {"convention": "cloture_moyenne_ecartee", "valeur": 18.0, "moyenne_code": "registre_operation_capital",
                  "residu_pct": 40.0}
    assert cm._roe_selon_ancien_test(reg) == ("cloture_moyenne_ecartee", 18.0)


def test_le_livrable_porte_le_residu_apres_dividende_et_les_dividendes_inconnus(comparaison):
    b = comparaison["synthese"]["residu_apres_dividende"]
    assert "|R + D| > 5 %" in b["regle"] and b["titres_examines"] == len(b["detail"])
    for s in b["dividende_inconnu"]:
        assert b["detail"][s]["dividende_mmad"] is None and b["detail"][s]["residu_apres_dividende_pct"] is None
    assert {"CTM", "BCP"} <= set(b["ecartes_par_le_residu"])
    for s, x in b["detail"].items():
        if x["dividende_mmad"] is not None:
            assert x["dividende_origine"] in ("tableau_variation", "flux_de_trésorerie", "calendrier"), s
    ex = comparaison["synthese"]["roe_d_exercice_par_titre"]
    for s in ("CTM", "BCP"):
        assert ex[s]["cause_residu_sur_piece"]["page"] in (68, 12) and ex[s]["dividende_exercice"]["page"] in (66, 12)
        assert abs(ex[s]["cause_residu_sur_piece"]["reste_pct"]) <= 5
        assert ex[s]["cause_residu_sur_piece"]["base_du_reste"].startswith("tableau de variation")
    assert ex["CTM"]["cause_residu_sur_piece"]["reste_pct"] == 0.0
    assert "RIS" not in b["dividende_inconnu"] and b["detail"]["RIS"]["dividende_origine"] == "calendrier"


def test_le_livrable_etiquette_tma_et_signale_waf(comparaison):
    s = comparaison["synthese"]
    assert "dividende exceptionnel de 67 DH payé le 11/12/2025" in s["dividendes_exceptionnels_dans_l_exercice"]["TMA"]["etiquette"]
    assert s["roe_d_exercice_par_titre"]["TMA"]["convention"] == "moyenne"
    w = s["roe_a_moins_de_0_5_point_d_un_palier"]["WAF"]
    assert w["seuil"] == 10.0 and w["ecart_points"] == 0.35 and "à 0,35 point du seuil de 10 %" in w["etiquette"]
    assert w["formule"] == "1026.036 ÷ moyenne(12566.785 − 2950.462 ; 14960.337 − 4747.429)"


def test_le_livrable_documente_atl_waf_atw(comparaison):
    doc = " ".join(comparaison["synthese"]["assurances_documentation"])
    for mot in ("IFRS 17", "NORMES MAROCAINES", "HORS BILAN", "terme à terme", "ATW", "INCLUS"):
        assert mot in doc, mot
    assert "ATW" not in comparaison["synthese"]["assurances_roe_hors_gains_latents_oci"]      # banque : hors règle


def test_le_livrable_empreinte_ses_deux_nouvelles_entrees(comparaison):
    emp = comparaison["empreintes_sha256"]
    assert "datasets/dividendes_bvc.json" in emp and "datasets/reserves_oci_assurances.json" in emp


def test_le_livrable_documente_les_trois_traitements_de_l_oci(comparaison):
    tr = comparaison["synthese"]["traitements_de_l_oci"]
    assert [x["traitement"].split()[0] for x in tr] == ["RETIRÉ", "CONSERVÉ", "NON"]
    assert [x["titres"] for x in tr][1:] == [["ATW"], ["MNG"]] and set(tr[0]["titres"]) == {"ATL", "SAF", "WAF"}
    assert all(x["raison"] and x["mesure"] for x in tr)
    assert tr[0]["mesure"]["WAF_roe_cloture_avec_oci"] == 6.86 and tr[0]["mesure"]["WAF_roe_cloture_hors_oci"] == 10.05
    assert abs(tr[1]["mesure"]["residu_apres_dividende_pct"]) < tr[1]["mesure"]["seuil_pct"]
    assert tr[2]["mesure"]["code"] == "residu_cause_sur_piece" and tr[2]["mesure"]["convention"] == "cloture_moyenne_ecartee"


def test_l_unite_des_gains_latents_de_waf_est_lisible(comparaison):
    doc = " ".join(comparaison["synthese"]["assurances_documentation"])
    assert "4,7 Md MAD" in doc and "4 747" in doc and "4,7 MMAD" not in doc
