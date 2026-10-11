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
