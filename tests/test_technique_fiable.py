"""Pilier technique neutralisé sur les titres peu liquides et au fixing.

⚠️ Pourquoi : rejoué sur trois ans (étape 0 du calibrage), le pilier
technique y annonce l'INVERSE de la suite. Règle : `pipeline/technique_fiable.py`.
Accord d'Abd Moutalib, 03/10/2026 (R8).

Les attendus sont écrits en dur, jamais recalculés par la fonction testée.
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.technique_fiable import SEUIL_DH, technique_non_fiable  # noqa: E402


def _bougies(n, prix, volume, plate=False):
    return [{"d": f"2026-09-{i + 1:02d}", "o": prix, "h": prix if plate else prix * 1.02,
             "l": prix if plate else prix * 0.98, "c": prix, "v": volume} for i in range(n)]


def test_le_seuil_est_celui_de_l_etape_0():
    assert SEUIL_DH == 125_947


def test_un_titre_liquide_en_continu_garde_son_pilier_technique():
    # 100 DH × 5 000 titres = 500 000 DH par séance, bougies à extrêmes réels
    assert technique_non_fiable(_bougies(20, 100.0, 5_000)) is None


def test_un_titre_peu_liquide_est_neutralise():
    # 100 DH × 1 000 titres = 100 000 DH < 125 947
    m = technique_non_fiable(_bougies(20, 100.0, 1_000))
    assert m["motif"] == "peu liquide" and m["montant_median_dh"] == 100_000


def test_un_titre_au_fixing_est_neutralise_meme_s_il_echange_beaucoup():
    m = technique_non_fiable(_bougies(20, 100.0, 50_000, plate=True))
    assert m["motif"] == "coté au fixing" and m["seances_plates"] == 20


def test_seules_les_20_dernieres_seances_echangees_comptent():
    # 30 vieilles séances illiquides, puis 20 liquides : le titre est lisible
    vieilles = _bougies(30, 100.0, 100)
    recentes = _bougies(20, 100.0, 5_000)
    sans_echange = [{**b, "v": 0} for b in _bougies(5, 100.0, 0)]
    assert technique_non_fiable(vieilles + recentes + sans_echange) is None


def test_sans_aucune_seance_echangee_le_titre_est_neutralise():
    assert technique_non_fiable([{**b, "v": 0} for b in _bougies(20, 100.0, 0)])["seances_echangees"] == 0
    assert technique_non_fiable(None)["motif"] == "aucune chandelle"


# ⚠️ 06/11/2026 — retrait de la note v5.3 (lot 2). La neutralisation reversait
# la part du technique au fondamental (`get_weights`) et plafonnait ACHETER à
# SURVEILLER (`_signal_publie`) : les deux sont retirés avec la note. Le motif
# reste publié (`technique_neutralise`), lu par la règle A
# (`_meta.non_comparable`) et par le pilier technique v2 en mode ombre.
# Tests d'origine : archive/tests/test_technique_fiable_lot2_2026-11-06.py.

def test_le_motif_reste_publie_et_ne_module_plus_aucune_note():
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert '"technique_neutralise": _tech_nf,' in src
    assert "tech_non_fiable" not in src.split("def run(dry_run=False")[1]
