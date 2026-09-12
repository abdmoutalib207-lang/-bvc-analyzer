#!/usr/bin/env python3
"""La couche candidate ne doit jamais toucher aux chandelles publiées.

⚠️ POURQUOI CE FICHIER EXISTE
Proposer une correction et l'appliquer sont deux décisions distinctes. Le
projet a déjà réécrit un historique en croyant l'améliorer — les cours
pré-split de MNG, réinjectés par un run qui « rafraîchissait ». Ici, la
séparation est vérifiée, pas promise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))
DOSSIER = RACINE / "datasets" / "historiques_candidats"
NIVEAUX = {"etabli_par_la_mesure", "etabli_par_l_absence", "hypothese_a_confirmer"}


def _propositions():
    if not DOSSIER.exists():
        pytest.skip("aucune couche candidate")
    for f in sorted(DOSSIER.glob("corrections_*.json")):
        yield f, json.loads(f.read_text(encoding="utf-8"))


def test_les_corrections_vivent_hors_des_chandelles_publiees():
    """⚠️ Une proposition qui s'écrirait dans pipeline/candles/ ne serait plus
    une proposition."""
    for f, _ in _propositions():
        assert "candles" not in f.parts, f"{f} est dans le dossier des chandelles"
    src = (RACINE / "pipeline" / "corrections_candidates.py").read_text(encoding="utf-8")
    assert "SORTIE = RACINE / \"datasets\"" in src
    for interdit in ("candles_dir", "save_candle_file", "/ \"candles\""):
        assert interdit not in src, (
            f"le générateur de propositions touche aux chandelles : {interdit}")


def test_chaque_proposition_porte_son_niveau_de_preuve():
    """Sans niveau, une hypothèse se lit comme un fait."""
    vu = 0
    for f, r in _propositions():
        for p in r["propositions"]:
            vu += 1
            assert p["preuve"] in NIVEAUX, f"{f.name} : niveau inconnu {p['preuve']}"
            assert p.get("motif"), f"{f.name} : proposition sans motif"
    assert vu, "aucune proposition à vérifier"


def test_une_hypothese_ne_propose_aucun_remplacement():
    """⚠️ Corriger sur une hypothèse, c'est réécrire l'historique sur une
    conviction. Une proposition non établie SIGNALE, elle ne remplace pas."""
    for f, r in _propositions():
        for p in r["propositions"]:
            if p["preuve"] == "hypothese_a_confirmer":
                assert p["type"] == "signaler", (
                    f"{f.name} : une proposition de niveau hypothèse prétend "
                    f"« {p['type']} »")
                assert "remplacement" not in p and "ajout" not in p


def test_le_montant_en_dirhams_ne_devient_jamais_une_quantite():
    """Les deux grandeurs restent distinctes — aucune conversion."""
    for f, r in _propositions():
        for p in r["propositions"]:
            for b in p.get("remplacement", []) + p.get("ajout", []):
                assert "_volume_mad" in b, (
                    f"{f.name} : le montant en dirhams a disparu de la bougie")
                if b["_volume_mad"] and b["v"]:
                    assert b["v"] != b["_volume_mad"], (
                        f"{f.name} · {b['d']} : « v » porte le MONTANT en "
                        f"dirhams au lieu du nombre de titres")


def test_la_contamination_de_MSA_est_etablie_et_non_supposee():
    """⚠️ LE FAIT CENTRAL. Il doit reposer sur une mesure, pas sur un récit."""
    f = DOSSIER / "corrections_MSA.json"
    if not f.exists():
        pytest.skip("MSA non confronté")
    r = json.loads(f.read_text(encoding="utf-8"))
    rempl = [p for p in r["propositions"] if p["type"] == "remplacer"]
    assert rempl, "aucune proposition de remplacement pour MSA"
    p = rempl[0]
    assert p["preuve"] == "etabli_par_la_mesure"
    assert p["nombre"] == len(p["remplacement"]) == 22
    assert "22/22" in p["motif"] and "0/22" in p["motif"], (
        "le motif ne porte pas les deux décomptes qui établissent le fait")


def test_l_identite_est_exigee_avant_tout_rapprochement():
    """Le rapprochement doit s'ARRÊTER si l'identité n'est pas portée."""
    from confronter_historique import confronter
    src = (RACINE / "pipeline" / "confronter_historique.py").read_text(encoding="utf-8")
    i_id = src.index("identite_de_l_export(chemin)")
    i_cmp = src.index("brut = lire_export(chemin)")
    assert i_id < i_cmp, "les séries sont lues avant que l'identité soit établie"
    assert "_arret" in src, "aucun arrêt prévu quand l'identité n'est pas portée"


def test_un_defaut_d_echelle_n_est_pas_compte_comme_des_ecarts_isoles():
    """⚠️ SOT annonçait 519 écarts là où il y a UN défaut d'échelle sur un
    segment. Présenter un défaut unique comme 486 écarts trompe sur sa nature
    autant que sur son nombre."""
    f = DOSSIER / "corrections_SOT.json"
    if not f.exists():
        pytest.skip("SOT non confronté")
    r = json.loads(f.read_text(encoding="utf-8"))
    ech = [p for p in r["propositions"] if p["type"] == "remettre_a_l_echelle"]
    sig = [p for p in r["propositions"] if p["type"] == "signaler"]
    assert ech, "le défaut d'échelle de SOT n'est pas détecté"
    assert sig and sig[0]["nombre"] < ech[0]["nombre"], (
        "les séances du segment à l'échelle sont recomptées comme des écarts")


def test_aucune_suppression_hors_de_la_periode_couverte_par_l_export():
    """⚠️ Ma première version proposait de retirer 68 séances de HPS, dont 67
    ANTÉRIEURES au premier jour de l'export. L'export ne les cote pas parce
    qu'il commence plus tard — pas parce qu'elles n'ont pas eu lieu."""
    import sys as _s
    _s.path.insert(0, str(RACINE / "pipeline"))
    from corrections_candidates import _exp
    for f, r in _propositions():
        t = r["ticker"]
        try:
            bornes = (min(_exp(t)), max(_exp(t)))
        except Exception:
            continue
        for p in r["propositions"]:
            if p["type"] != "retirer":
                continue
            for d in p["seances"]:
                assert bornes[0] <= d <= bornes[1], (
                    f"{t} : suppression proposée pour {d}, hors de la période "
                    f"couverte par l'export {bornes}")


# ═══ CORRECTIONS DEMANDÉES PAR LA REVUE DU 12/09 ═══════════════════════════

def test_une_absence_n_est_jamais_comblee(): 
    """⚠️ SÉANCE SOT DU 24/06/2026 : l'export ne porte QUE la clôture (376).

    Le candidat fabriquait `o = h = l = 376` et `v = 0`. Un zéro fabriqué se
    lit comme « aucun échange » ; une bougie plate se lit comme « le cours n'a
    pas bougé ». Ni l'un ni l'autre n'a été observé.
    """
    f = DOSSIER / "corrections_SOT.json"
    if not f.exists():
        pytest.skip("SOT non confronté")
    r = json.loads(f.read_text(encoding="utf-8"))
    trouve = False
    for p in r["propositions"]:
        for b in p.get("ajout", []):
            if b["d"] != "2026-06-24":
                continue
            trouve = True
            assert b["c"] == 376.0
            for k in ("o", "h", "l", "v"):
                assert b[k] is None, f"le champ {k} est fabriqué : {b[k]}"
            assert set(b["_champs_absents"]) == {"o", "h", "l", "v"}
            assert b["_usages_interdits"] and b["_usages_possibles"]
    assert trouve, "la séance du 24/06 n'est pas proposée à l'ajout"


def test_aucun_coefficient_n_est_applique_en_bloc():
    """⚠️ « Le facteur observé voisin de 4,607 ne prouve pas la cause. »"""
    f = DOSSIER / "corrections_SOT.json"
    if not f.exists():
        pytest.skip("SOT non confronté")
    r = json.loads(f.read_text(encoding="utf-8"))
    for p in r["propositions"]:
        if p["type"] != "remettre_a_l_echelle":
            continue
        assert "facteur_a_corriger" not in p, (
            "le facteur est présenté comme une correction à appliquer")
        assert "facteur_observe" in p
        # ⚠️ On éprouve la PROPRIÉTÉ, pas une tournure : aucune valeur de
        # remplacement n'accompagne le facteur, et l'interdiction d'appliquer
        # en bloc est écrite noir sur blanc.
        assert "remplacement" not in p and "ajout" not in p, (
            "un facteur observé s'accompagne de valeurs à écrire")
        assert "en bloc" in p["_le_facteur_n_est_pas_une_cause"], (
            "l'interdiction d'appliquer le facteur en bloc n'est pas énoncée")
        assert p.get("_comparaison_ligne_a_ligne"), (
            "aucune comparaison ligne à ligne n'est désignée pour décider")


def test_le_journal_distingue_les_trois_series():
    """cours brut · cours sur la base retenue · notre cours — et les deux
    rapports. Les confondre produit des conclusions fausses."""
    f = DOSSIER / "journal_SOT_2024-05-14_2026-05-04.json"
    if not f.exists():
        pytest.skip("journal SOT absent")
    r = json.loads(f.read_text(encoding="utf-8"))
    l = r["lignes"][0]
    for k in ("cours_brut_operateur", "cours_sur_base_retenue", "notre_cours",
              "rapport_sur_base_brut", "rapport_sur_base_retenue"):
        assert k in l, f"{k} absent du journal"
    assert l["cours_brut_operateur"] != l["cours_sur_base_retenue"], (
        "les deux bases sont confondues alors qu'un split les sépare")


def test_le_journal_conserve_l_ancien_etat_champ_par_champ():
    f = DOSSIER / "journal_MSA_2026-05-13_2026-06-16.json"
    if not f.exists():
        pytest.skip("journal MSA absent")
    r = json.loads(f.read_text(encoding="utf-8"))
    assert r["seances"] == 22
    for l in r["lignes"]:
        for k in ("o", "h", "l", "c", "v"):
            c = l["champs"][k]
            assert "ancien" in c and "propose" in c and "etat" in c


def test_la_base_des_quantites_est_declaree_apres_un_split():
    """⚠️ Le 22/06, les prix de Managem sont divisés par dix ; `v` garde 715.
    Sans base déclarée, un calcul ultérieur mélange deux échelles."""
    import sys as _s
    _s.path.insert(0, str(RACINE / "pipeline"))
    from confronter_historique import lire_export, ajuster_splits
    from pathlib import Path as _P
    brut = lire_export(sorted((RACINE / "sources" / "MNG").glob("*.csv"))[-1])["seances"]
    aju = ajuster_splits("MNG", brut)["seances"]
    v = aju["2026-06-22"]
    assert v["_base_des_quantites"].startswith("ANTÉRIEURE")
    assert "postérieure" in v["_base_des_prix"]
    assert v["titres_echanges_base_posterieure"] == round(v["titres_echanges"] * 10)


def test_notre_profondeur_n_est_pas_comptee_comme_fantome():
    """⚠️ 67 séances d'HPS et de Managem précèdent le début de l'export. Les
    appeler « fantômes » est faux, même si on ne les supprime pas."""
    for t in ("HPS", "MNG"):
        f = DOSSIER / f"confrontation_{t}.json"
        if not f.exists():
            continue
        c = json.loads(f.read_text(encoding="utf-8"))["couverture"]
        assert len(c["fantomes"]) == 1, f"{t} : {len(c['fantomes'])} fantômes annoncés"
        assert c["notre_profondeur_hors_export"]["nombre"] == 67
    doc = (RACINE / "docs" / "HISTORIQUES_LOT2.md").read_text(encoding="utf-8")
    assert "notre profondeur" in doc, (
        "la synthèse ne distingue pas profondeur et fantôme")
