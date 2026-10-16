"""Règle UNIQUE de l'écart de dette nette (16/10/2026).

Relecture externe : ADI était contesté pour 4,5 % d'écart entre le chiffre de la
société et la dette nette recalculée au bilan, pendant que VCNE restait noté
malgré 18,5 %, parce que le chiffre de Vicenne n'était rangé que dans
`_ecarts_mesures`. La règle, écrite en tête du registre CONTESTES de
`pipeline/smart_money/fond_score.py` :
  1. le chiffre de la société est rangé pour TOUS dans `faits.endettement_net` ;
  2. écart ≤ SEUIL_ECART_DETTE : concordant ;
  3. au-delà, accepté seulement si expliqué sur pièce — définition de la
     société citée, éléments nommés par un poste de la liste admise, chiffrés,
     page et citation — et que le résidu recalculé reste sous le même seuil ;
     sinon CONTESTÉ.
"""
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.smart_money import fond_score as fg  # noqa: E402
from pipeline.smart_money import fond_score_sectoriel as fs  # noqa: E402

FAITS = json.loads((RACINE / "pipeline" / "faits_financiers.json").read_text(encoding="utf-8"))
_FOND = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))
FOND = _FOND.get("societes", _FOND)


def _dn(sym):
    return FOND[sym]["ratios_publies"]["dette_nette"]


def _contestee_reelle(sym):
    return fs._dette_nette_contestee(_dn(sym), FAITS[sym])


def _faits(endettement, rapprochement=None):
    en = {"valeur": endettement, "page": 1}
    if rapprochement is not None:
        en["rapprochement"] = rapprochement
    return {"exercice": 2025, "faits": {"endettement_net": en}}


def _rap(base, elements, definition=True):
    r = {"etabli": True, "dette_nette_base": base, "elements": elements}
    if definition:
        r["definition_de_la_societe"] = {"page": 2, "citation": "Endettement net = ... +/- comptes courants"}
    return r


# ── seuil et liste : un seul endroit ─────────────────────────────────────────

def test_le_seuil_et_les_explications_vivent_dans_le_registre():
    assert fs.ECART_DETTE_MAX is fg.SEUIL_ECART_DETTE == 0.02
    assert fs.EXPLICATIONS_ECART_DETTE_ADMISES is fg.EXPLICATIONS_ECART_DETTE_ADMISES
    for poste in ("ifrs16_location", "derives_couverture", "comptes_courants_associes",
                  "mise_en_equivalence", "depots_tresorerie_bloquee", "titres_de_placement"):
        assert poste in fg.EXPLICATIONS_ECART_DETTE_ADMISES


# ── cas construits ───────────────────────────────────────────────────────────

def test_ecart_sous_le_seuil_concordant_sans_explication():
    # 1 000 contre 1 015 : 1,5 % ≤ 2 %
    assert fs._dette_nette_contestee({"valeur": 1000.0}, _faits(1015.0)) is None


def test_ecart_explique_sur_piece_par_un_poste_admis_est_accepte():
    rap = _rap(100.0, [{"poste": "comptes_courants_associes", "valeur": -500.0, "page": 43,
                        "citation": "Comptes d'associés 500 000 000"}])
    assert fs._dette_nette_contestee({"valeur": 100.0}, _faits(-400.0, rap)) is None


def test_ecart_non_explique_est_conteste():
    motif = fs._dette_nette_contestee({"valeur": -368.7}, _faits(-311.0))
    assert motif and "grandeur contestée" in motif and "18.6%" in motif


@pytest.mark.parametrize("element,definition", [
    ({"poste": "a_l_appreciation", "valeur": -500.0, "page": 43, "citation": "x"}, True),   # poste hors liste
    ({"valeur": -500.0, "page": 43, "citation": "x"}, True),                                 # poste non nommé
    ({"poste": "comptes_courants_associes", "valeur": -500.0, "page": 43, "citation": "x"}, False),  # sans définition
    ({"poste": "comptes_courants_associes", "valeur": -450.0, "page": 43, "citation": "x"}, True),  # résidu 50/400 > 2 %
])
def test_une_explication_hors_regle_ne_leve_pas_la_contestation(element, definition):
    rap = _rap(100.0, [element], definition)
    assert "grandeur contestée" in fs._dette_nette_contestee({"valeur": 100.0}, _faits(-400.0, rap))


# ── données réelles ──────────────────────────────────────────────────────────

def test_adi_et_vcne_sont_traites_de_la_meme_facon():
    """L'incohérence relevée : 4,5 % contesté, 18,5 % libre. Les deux sont contestés."""
    assert "grandeur contestée" in _contestee_reelle("ADI")
    assert "grandeur contestée" in _contestee_reelle("VCNE")
    for s in ("ADI", "VCNE"):
        rap = FAITS[s]["faits"]["endettement_net"]["rapprochement"]
        assert rap["etabli"] is False and "NON ÉTABLIE" in rap["cause"], s


@pytest.mark.parametrize("sym", ["MNG", "SMI", "COL"])
def test_les_ecarts_expliques_sur_piece_sont_acceptes(sym):
    assert _contestee_reelle(sym) is None
    rap = FAITS[sym]["faits"]["endettement_net"]["rapprochement"]
    assert rap["definition_de_la_societe"]["page"] and rap["definition_de_la_societe"]["citation"]
    assert all(e["poste"] in fg.EXPLICATIONS_ECART_DETTE_ADMISES for e in rap["elements"])
    total = _dn(sym)["valeur"] + sum(e["valeur"] for e in rap["elements"])
    en = FAITS[sym]["faits"]["endettement_net"]["valeur"]
    assert abs(total - en) / abs(en) <= fg.SEUIL_ECART_DETTE


def test_le_chiffre_de_la_societe_est_range_au_meme_endroit_pour_tous():
    """Un chiffre de la société consigné dans `_ecarts_mesures` doit aussi être le
    fait `endettement_net` que lit le contrôle : c'est ce qui manquait à VCNE."""
    for sym, e in FAITS.items():
        if not isinstance(e, dict) or "faits" not in e:
            continue
        rapport = ((e.get("_ecarts_mesures") or {}).get("dette_nette") or {}).get("rapport")
        if rapport is None:
            continue
        en = e["faits"].get("endettement_net")
        assert en and en["valeur"] == rapport and isinstance(en.get("page"), int), sym


def test_tout_endettement_net_porte_sa_page():
    for sym, e in FAITS.items():
        en = (e.get("faits") or {}).get("endettement_net") if isinstance(e, dict) else None
        if en:
            assert isinstance(en.get("page"), int), sym


def test_le_registre_des_contestations_suit_la_regle():
    c = fg.charger_contestations(FOND, FAITS)
    try:
        assert {"ADI", "MUT", "VCNE"} <= set(c)
        assert not {"MNG", "SMI", "COL", "IAM", "LBV", "MSA", "DTT", "HAL"} & set(c)
        # contestée : ROIC et dette nette/EBITDA ne sont plus lus par la porte unique
        assert fg.ratio_effectif(FOND["VCNE"], "VCNE", "roic") is None
        assert fg.ratio_effectif(FOND["VCNE"], "VCNE", "dette_nette_ebitda") is None
    finally:
        fg.CONTESTES.clear()
