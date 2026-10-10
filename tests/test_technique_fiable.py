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


def test_la_part_du_technique_revient_au_fondamental():
    import update_data
    w = update_data.get_weights({"market_status": "CLOSED", "tech_non_fiable": True})
    assert w["technique"] == 0.0
    assert w["comportemental"] == 0.0
    assert w["fondamental"] == 1.0


def test_la_note_d_un_titre_neutralise_ne_depend_plus_du_technique():
    """Invariance : technique à 1 ou à 9, la note est la même — le fondamental."""
    import update_data
    ctx = {"market_status": "CLOSED", "tech_non_fiable": True}
    a = update_data.compute_v53("ZZZ", 1.0, 4.0, 0, 0, ctx)
    b = update_data.compute_v53("ZZZ", 9.0, 4.0, 0, 0, ctx)
    assert a["v53"] == b["v53"] == 4.0
    assert a["poids"]["t"] == 0


def test_sans_drapeau_rien_ne_change():
    import update_data
    w = update_data.get_weights({"market_status": "CLOSED"})
    assert w["technique"] > 0


def test_le_verdict_d_un_titre_peu_liquide_est_plafonne(monkeypatch):
    """04/10/2026 : « ACHETER » plafonné à « SURVEILLER ★ » sur un titre au
    technique neutralisé (peu liquide, fixing). La note chiffrée reste.
    Depuis le 10/10/2026 la règle vit dans `_signal_publie` : prouvée ici par
    son comportement plutôt que par le texte du code."""
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setattr(update_data, "sans_comptes", lambda t: None)
    nf = {"motif": "titre au fixing"}
    assert update_data._signal_publie("ZZZ", "ACHETER ★★", nf, None) == (
        "SURVEILLER ★", "ACHETER plafonné : titre au fixing")
    # Seul ACHETER est plafonné : les autres paliers passent tels quels.
    for sig in ("SURVEILLER ★", "ATTENDRE", "ÉVITER", "ÉVITER FORT"):
        assert update_data._signal_publie("ZZZ", sig, nf, None) == (sig, None)
    # Sans neutralisation du technique, ACHETER reste ACHETER.
    assert update_data._signal_publie("ZZZ", "ACHETER ★★", None, None) == ("ACHETER ★★", None)
    # « Données insuffisantes » prime, et aucun verdict plafonné n'est annoncé.
    assert update_data._signal_publie("ZZZ", "ACHETER ★★", nf, 3) == ("Données insuffisantes", None)
    assert update_data._signal_publie("ZZZ", "ACHETER ★★", nf, None, sans_note=True) == (
        "Données insuffisantes", None)
    assert '"verdict_plafonne"' in (RACINE / "update_data.py").read_text(encoding="utf-8")
