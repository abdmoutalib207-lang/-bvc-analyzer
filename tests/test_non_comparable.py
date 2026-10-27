"""Titres très peu liquides NON COMPARABLES (règle A) et foncières sans note par
métier (règle B) — 27/10/2026, accord R8 d'Abd Moutalib.

Aucune note ne change : seuls le signal publié, le champ `_meta.non_comparable`
et l'ordre du classement du terminal. Mesure avant/après sur le même origin/main
(essai à blanc hors réseau) : 31 signaux changent, 29 par la règle A, 2 par la
règle B (ARD, IMI) ; zéro note v53 modifiée.
"""
import copy
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

def test_seuil_dans_bvc_config_et_version_du_score():
    assert bvc_config.SEUIL_NON_COMPARABLE_DH == 100_000
    assert "RÈGLE A" in (RACINE / "bvc_config.py").read_text(encoding="utf-8")
    assert bvc_config.SCORE_VERSION == "v5.3-non-comparable-2026-10-27"
    assert U.SIG_NON_COMPARABLE == NC


def test_condition_technique_neutralisee_et_mediane_sous_le_seuil():
    assert U.non_comparable(None) is None                      # technique lisible
    assert U.non_comparable(_tn(100_000)) is None              # seuil exclu
    assert U.non_comparable(_tn(125_000, "coté au fixing")) is None
    assert U.non_comparable(_tn(99_999)) == {"motif": "titre peu liquide",
                                             "montant_median_dh": 99_999, "seuil": 100_000}
    # Sans séance échangée, la médiane est absente : comptée 0 (convention de la mesure).
    sans = U.non_comparable({"motif": "aucune séance échangée", "seances_echangees": 0})
    assert sans == {"motif": "aucune séance échangée", "montant_median_dh": None, "seuil": 100_000}


# ── La précédence ───────────────────────────────────────────────────────────

def test_precedence_suspendu_puis_donnees_insuffisantes_puis_non_comparable(monkeypatch):
    nc = U.non_comparable(_tn(754))
    assert U._signal_publie("X", "SURVEILLER ★", _tn(754), None, non_comparable=nc) == (NC, None)
    # Avant « Couverture partielle », et avant le plafond de liquidité du verdict.
    assert U._signal_publie("X", "ACHETER ★★", _tn(754), None, couverture_partielle=True,
                            non_comparable=nc, fonciere_sans_note=True) == (NC, None)
    # « Données insuffisantes » garde la priorité (reprise, sans note, sans comptes).
    assert U._signal_publie("X", "ATTENDRE", _tn(754), 3, non_comparable=nc)[0] == "Données insuffisantes"
    assert U._signal_publie("X", None, _tn(754), None, sans_note=True, non_comparable=nc)[0] == \
        "Données insuffisantes"
    monkeypatch.setattr(U, "sans_comptes", lambda t: {"motif": "x"})
    assert U._signal_publie("X", "ATTENDRE", _tn(754), None, non_comparable=nc)[0] == "Données insuffisantes"
    monkeypatch.setattr(U, "_suspendu_maintenant", lambda t: True)
    assert U._signal_publie("X", "ATTENDRE", _tn(754), None, non_comparable=nc)[0] == "SUSPENDU"


@pytest.mark.parametrize("sig", ["ACHETER ★★", "SURVEILLER ★", "ATTENDRE", "ÉVITER", "ÉVITER FORT"])
def test_aucun_verdict_de_palier_n_est_emis(sig):
    s, plafond = U._signal_publie("X", sig, _tn(5_000), None, non_comparable=U.non_comparable(_tn(5_000)))
    assert (s, plafond) == (NC, None)


def test_sans_regle_rien_ne_change():
    """Titre liquide : verdict et plafond comme avant le 27/10."""
    assert U._signal_publie("X", "ATTENDRE", None, None) == ("ATTENDRE", None)
    assert U._signal_publie("X", "ACHETER ★★", _tn(110_000), None)[0] == "SURVEILLER ★"


def test_le_champ_meta_suit_le_signal_et_seulement_lui():
    nc = U.non_comparable(_tn(754))
    e = {"sig": NC, "_meta": {}}
    U._poser_non_comparable(e, nc)
    assert e["_meta"]["non_comparable"] == nc
    e["sig"] = "Données insuffisantes"
    U._poser_non_comparable(e, nc)
    assert "non_comparable" not in e["_meta"]


# ── Règle B : foncière sans note par métier (second passage) ─────────────────

def _passe1(sym, sig_v53="ATTENDRE", tech_nf=None):
    return {"score_tech": 5.0, "ctx": {"market_status": "CLOSED"}, "tech_nf": tech_nf,
            "depuis_reprise": None, "price": 100.0, "ma20": None, "ma50": None,
            "meta_args": (sym, "cdg", "2026-10-27", {}, None, False), "meta_kw": {},
            "sig_v53": sig_v53, "sans_note": False, "couv_partielle": False,
            "non_comparable": U.non_comparable(tech_nf)}


def _fiche(sym, sig="ATTENDRE"):
    return {"symbol": sym, "price": 100.0, "pb": None, "rsi": 50, "_meta": {"confidence": 5},
            "score_fond": 4.7, "v53": 4.7, "sig": sig, "setup": "NEUTRE", "verdict_plafonne": None}


def _brancher(monkeypatch, familles):
    from pipeline.smart_money import fond_score_sectoriel as F
    monkeypatch.setattr(F, "noter_univers", lambda syms, *a, **k: {
        s: {"note": None if familles[s] == "fonciere" else 5.0, "famille": familles[s], "partielle": False}
        for s in syms})
    monkeypatch.setattr(F, "detail_publie", lambda r: {"famille": r["famille"], "note": r["note"]})


def test_regle_b_fonciere_sans_note_metier_devient_couverture_partielle(monkeypatch):
    _brancher(monkeypatch, {"ARD": "fonciere", "ADH": "promoteur", "BAL": "fonciere"})
    out = [_fiche("ARD"), _fiche("ADH"), _fiche("BAL", NC)]
    p1 = {"ARD": _passe1("ARD"), "ADH": _passe1("ADH"), "BAL": _passe1("BAL", "SURVEILLER ★", _tn(754))}
    out[2]["_meta"]["non_comparable"] = p1["BAL"]["non_comparable"]
    avant = copy.deepcopy(out)
    U.appliquer_note_sectorielle(out, p1, fondamentaux={}, bpa={}, faits={}, s1={}, publier=False)
    ard, adh, bal = out
    assert (ard["sig"], ard["verdict_plafonne"]) == ("Couverture partielle", None)
    assert adh["sig"] == "ATTENDRE"                       # pas une foncière : inchangé
    assert bal["sig"] == NC and bal["_meta"]["non_comparable"]["montant_median_dh"] == 754   # A avant B
    # Étiquette seulement : note, score fondamental et rang ne bougent pas.
    for a, b in zip(avant, out):
        assert (a["v53"], a["score_fond"]) == (b["v53"], b["score_fond"])


def test_regle_b_une_note_indisponible_n_est_pas_une_fonciere_sans_note(monkeypatch):
    from pipeline.smart_money import fond_score_sectoriel as F
    _brancher(monkeypatch, {"ARD": "fonciere"})
    monkeypatch.setattr(F, "detail_publie", lambda r: {"famille": "fonciere", "note": None, "indisponible": True})
    out = [_fiche("ARD")]
    U.appliquer_note_sectorielle(out, {"ARD": _passe1("ARD")}, fondamentaux={}, bpa={}, faits={}, s1={},
                                 publier=False)
    assert out[0]["sig"] == "ATTENDRE"


# ── Le terminal lit le CHAMP, pas le libellé ─────────────────────────────────

def test_terminal_lit_meta_non_comparable_et_garde_la_precedence():
    assert ("const nonComparable=r=>{const m=meta(r);return m.susp||m.conf<=1?null:"
            "(m.non_comparable||null);};") in SRC
    assert 'r.sig==="Non comparable' not in SRC and "Non comparable (liquidité)" not in SRC


def test_terminal_note_grise_sans_palier():
    assert "if(couvPartielle(r)||nonComparable(r))return null;" in SRC     # couleurNote
    assert "const nc=nonComparable(r);if(nc)return texteNonComparable(nc);" in SRC   # palierTexte
    assert "non comparable — titre peu liquide (médiane ${dhSeance(nc.montant_median_dh)})" in SRC
    assert 'className="pastille-non-comparable"' in SRC


def test_terminal_classe_les_non_comparables_apres_les_comparables():
    """Le VRAI comparateur du classement, exécuté par node : un titre non
    comparable noté 9 passe derrière un comparable noté 0 ; une note absente
    reste en dernier ; la suspension prime (pas de champ lu)."""
    import json
    from test_raccordement_composantes import NOUVEAU, P7030, _consts_js, _executer_js, _fonctions_js
    m = re.search(r'if\(sort==="v53"\)\{(.*?)\n    \}', SRC, re.S)
    assert m, "la branche de tri sur v53 est introuvable"
    meta5 = {"confidence": 5}
    lignes = [dict(NOUVEAU, symbol="NC9", score_fond=9.0, score_tech=9.0,
                   _meta=dict(meta5, non_comparable={"motif": "titre peu liquide",
                                                     "montant_median_dh": 754, "seuil": 100000})),
              dict(NOUVEAU, symbol="ABSENT", score_fond=None, score_tech=None, _meta=meta5),
              dict(NOUVEAU, symbol="ZERO", score_fond=0.0, score_tech=0.0, _meta=meta5),
              dict(NOUVEAU, symbol="HAUT", score_fond=8.0, score_tech=8.0, _meta=meta5),
              dict(NOUVEAU, symbol="NC2", score_fond=2.0, score_tech=2.0,
                   _meta=dict(meta5, non_comparable={"motif": "x", "montant_median_dh": 1, "seuil": 100000}))]
    script = (_consts_js("meta", "nonComparable") + "\n"
              + _fonctions_js("composantesScore", "composantesManquantes", "computeDisplayScore")
              + "\nconst scoreMode = " + json.dumps(P7030) + ";"
              + "\nfunction comparer(a, b){" + m.group(1) + "\n}"
              + "\nconst lignes = " + json.dumps(lignes) + ";"
              + "\nconsole.log(lignes.sort(comparer).map(x=>x.symbol).join(','));")
    assert _executer_js(script) == "HAUT,ZERO,NC9,NC2,ABSENT"


def test_accueil_exclut_les_non_comparables_des_mieux_notes():
    assert "meta(r).conf>=2&&r.v53!=null&&!nonComparable(r)" in SRC


def test_fiche_bandeau_et_guide():
    assert 'label="Non comparable — titre peu liquide"' in SRC
    assert 'className="bandeau-non-comparable"' in SRC
    guide = SRC[SRC.index("const Guide=("):]
    guide = guide[:guide.index("\n};\n")]
    assert '<L titre="Note non comparable">' in guide
    seuil = f"{bvc_config.SEUIL_NON_COMPARABLE_DH:,}".replace(",", " ")
    assert f"moins de {seuil} DH échangés par séance" in guide


def test_index_compile_depuis_la_source():
    """index.html est la COMPILATION de terminal.src.html : la règle doit y être."""
    assert "pastille-non-comparable" in COMPILE and "bandeau-non-comparable" in COMPILE
    assert re.search(r"non_comparable", COMPILE)
