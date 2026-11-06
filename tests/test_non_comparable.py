"""Titres très peu liquides NON COMPARABLES (règle A) et foncières sans note par
métier (règle B) — 27/10/2026, accord R8 d'Abd Moutalib.

Aucune note ne change : seuls le signal publié, le champ `_meta.non_comparable`
et l'ordre du classement du terminal. Mesure avant/après sur le même origin/main
(essai à blanc hors réseau) : 31 signaux changent, 29 par la règle A, 2 par la
règle B (ARD, IMI) ; zéro note v53 modifiée.

⚠️ 06/11/2026 — retrait de la note v5.3 (lot 2). Le signal « Non comparable
(liquidité) » et la règle B (« Couverture partielle ») partent avec `sig`. Il
reste la règle A dans `_meta.non_comparable`, décidée par sa condition
(`non_comparable_publie`) et lue par la vue PER du terminal. Les tests du
signal sont archivés dans `archive/tests/test_non_comparable_lot2_2026-11-06.py`.
"""

import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
COMPILE = (RACINE / "index.html").read_text(encoding="utf-8")

import bvc_config  # noqa: E402
import update_data as U  # noqa: E402

NC = "Non comparable (liquidité)"


@pytest.fixture(autouse=True)
def _ni_suspendu_ni_sans_comptes(monkeypatch):
    monkeypatch.setattr(U, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setattr(U, "sans_comptes", lambda t: None)


def _tn(med, motif="peu liquide et coté au fixing"):
    return {"motif": motif, "montant_median_dh": med, "seances_plates": 20, "seances_echangees": 20}


# ── Le seuil et la condition ────────────────────────────────────────────────

def test_seuil_dans_bvc_config_et_plus_de_signal():
    assert bvc_config.SEUIL_NON_COMPARABLE_DH == 100_000
    assert "RÈGLE A" in (RACINE / "bvc_config.py").read_text(encoding="utf-8")
    # 06/11/2026 : plus de version de la note v5.3, plus de libellé de signal.
    assert not hasattr(bvc_config, "SCORE_VERSION")
    assert not hasattr(U, "SIG_NON_COMPARABLE") and not hasattr(U, "_signal_publie")


def test_condition_technique_neutralisee_et_mediane_sous_le_seuil():
    assert U.non_comparable(None) is None                      # technique lisible
    assert U.non_comparable(_tn(100_000)) is None              # seuil exclu
    assert U.non_comparable(_tn(125_000, "coté au fixing")) is None
    assert U.non_comparable(_tn(99_999)) == {"motif": "titre peu liquide",
                                             "montant_median_dh": 99_999, "seuil": 100_000}
    # Sans séance échangée, la médiane est absente : comptée 0 (convention de la mesure).
    sans = U.non_comparable({"motif": "aucune séance échangée", "seances_echangees": 0})
    assert sans == {"motif": "aucune séance échangée", "montant_median_dh": None, "seuil": 100_000}


# ── La précédence (dans le champ, depuis le retrait du signal) ─────────────

def test_le_champ_meta_suit_la_condition_et_ses_priorites(monkeypatch):
    """06/11/2026 (retrait de la note v5.3, lot 2) : `_meta.non_comparable` ne
    dépend plus du signal. Il est posé par la condition de liquidité, avec les
    priorités que le signal lui imposait : suspension, reprise récente, société
    sans comptes, note fondamentale absente."""
    nc = U.non_comparable(_tn(754))
    assert U.non_comparable_publie("X", nc, None, False) == nc
    assert U.non_comparable_publie("X", None, None, False) is None          # titre liquide
    assert U.non_comparable_publie("X", nc, 3, False) is None               # reprise récente
    assert U.non_comparable_publie("X", nc, None, True) is None             # sans note
    monkeypatch.setattr(U, "sans_comptes", lambda t: {"motif": "x"})
    assert U.non_comparable_publie("X", nc, None, False) is None            # sans comptes
    monkeypatch.setattr(U, "sans_comptes", lambda t: None)
    monkeypatch.setattr(U, "_suspendu_maintenant", lambda t: True)
    assert U.non_comparable_publie("X", nc, None, False) is None            # suspendu
    e = {"_meta": {}}
    U._poser_non_comparable(e, nc)
    assert e["_meta"]["non_comparable"] == nc
    U._poser_non_comparable(e, None)
    assert "non_comparable" not in e["_meta"]


def test_la_condition_ne_lit_aucun_signal():
    import inspect
    src = inspect.getsource(U.non_comparable_publie) + inspect.getsource(U._poser_non_comparable)
    assert '"sig"' not in src and "SIG_NON_COMPARABLE" not in src


# ── Le second passage ne touche plus le champ en mode comparaison ────────────
# Règle B (foncière sans note par métier → « Couverture partielle ») : retirée
# avec le signal le 06/11/2026.

def _passe1(sym, tech_nf=None):
    return {"tech_nf": tech_nf, "depuis_reprise": None,
            "meta_args": (sym, "cdg", "2026-10-27", {}, None, False), "meta_kw": {},
            "sans_note": False, "non_comparable": U.non_comparable(tech_nf)}


def test_le_second_passage_garde_le_champ_et_n_ajoute_aucun_signal(monkeypatch):
    from pipeline.smart_money import fond_score_sectoriel as F
    monkeypatch.setattr(F, "noter_univers", lambda syms, *a, **k: {
        s: {"note": None if s != "ADH" else 5.0, "famille": "fonciere" if s != "ADH" else "promoteur",
            "partielle": False} for s in syms})
    monkeypatch.setattr(F, "detail_publie", lambda r: {"famille": r["famille"], "note": r["note"]})
    out = [{"symbol": s, "price": 100.0, "pb": None, "rsi": 50, "_meta": {"confidence": 5}}
           for s in ("ARD", "ADH", "BAL")]
    p1 = {"ARD": _passe1("ARD"), "ADH": _passe1("ADH"), "BAL": _passe1("BAL", _tn(754))}
    out[2]["_meta"]["non_comparable"] = p1["BAL"]["non_comparable"]
    U.appliquer_note_sectorielle(out, p1, fondamentaux={}, bpa={}, faits={}, s1={}, publier=False)
    assert out[2]["_meta"]["non_comparable"]["montant_median_dh"] == 754
    assert "non_comparable" not in out[0]["_meta"] and "non_comparable" not in out[1]["_meta"]
    for e in out:
        assert not {"sig", "verdict_plafonne", "v53", "score_fond", "setup"} & set(e)


# ── Le terminal : la règle A n'est plus affichée (06/11/2026) ────────────────
#
# Du 27/10 au 05/11/2026, le terminal appliquait la règle A à la NOTE v5.3 :
# note grise sans palier, mention « non comparable », rang après les titres
# comparables, exclusion des « mieux notés », entrée du guide. Le 06/11/2026,
# la note v5.3 quitte l'écran (décision d'Abd Moutalib) et le Score BVC, qui
# a son propre facteur de liquidité, devient le score unique : ces six
# affichages partent avec la note qu'ils qualifiaient. Le MOTEUR, lui, garde
# la règle A (tests ci-dessus) et publie toujours `_meta.non_comparable`. Il en reste à l'écran la mention de liquidité de la
# vue PER, qui lit le CHAMP — jamais un libellé.

def test_terminal_lit_meta_non_comparable_et_garde_la_precedence():
    """Vue PER : le champ du moteur, avec la même précédence que la règle
    (suspension et confiance ≤ 1 d'abord)."""
    assert "m_=meta(r),nco=m_.susp||m_.conf<=1?null:(m_.non_comparable||null);" in SRC
    assert 'r.sig==="Non comparable' not in SRC and NC not in SRC


def test_terminal_n_applique_plus_la_regle_a_a_un_score():
    """Le Score BVC se classe sur sa seule valeur : aucune relégation tirée de
    la règle A, aucune pastille « non comparable », aucune entrée de guide."""
    for disparu in ("const nonComparable", "pastille-non-comparable", "bandeau-non-comparable",
                    "texteNonComparable", '<L titre="Note non comparable">',
                    "Non comparable — titre peu liquide"):
        assert disparu not in SRC, disparu
    tri = re.search(r'if\(sort==="bvc"\)\{(.*?)\n    \}', SRC, re.S).group(1)
    assert "non_comparable" not in tri and "nonComparable" not in tri


def test_index_compile_depuis_la_source():
    """index.html est la COMPILATION de terminal.src.html : la vue PER y lit le champ."""
    assert "pastille-non-comparable" not in COMPILE and "bandeau-non-comparable" not in COMPILE
    assert re.search(r"non_comparable", COMPILE)
